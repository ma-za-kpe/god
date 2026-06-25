// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./SoulNFT.sol";

/**
 * @title RentCollector
 * @notice The immutable economic spine of the God Project.
 *         Enforces Law 0: every agent pays rent or dies.
 *         The creator's only remaining power after Phase 3 is endWorld().
 *
 * @dev Deployed once, never upgraded. Immutable by design.
 *      creator address is set at deploy and cannot be changed.
 */
contract RentCollector is ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ─── Immutable State ──────────────────────────────────────────────

    /// @notice The creator wallet. Receives all rent. Set once at deploy.
    address public immutable creator;

    /// @notice USDC token contract (6 decimals on Base).
    IERC20 public immutable usdc;

    /// @notice Soul NFT contract — minted at birth, burned at death.
    SoulNFT public immutable soulNft;

    // ─── Mutable State (governance-adjustable, not creator-arbitrary) ─

    /// @notice Base rent amount in USDC per period (6 decimals).
    uint256 public rentAmount;

    /// @notice Seconds between rent payments.
    uint256 public rentPeriod;

    /// @notice Seconds of grace after missed payment before throttle.
    uint256 public gracePeriod;

    /// @notice Maximum missed payments before deletion is scheduled.
    uint256 public maxMissedPayments;

    // ─── endWorld timelock ────────────────────────────────────────────

    /// @notice Timestamp when endWorld was queued. 0 = not queued.
    uint256 public endWorldQueuedAt;

    /// @notice How long the timelock lasts (default: 30 days).
    uint256 public constant END_WORLD_TIMELOCK = 30 days;

    /// @notice True after endWorld has been executed.
    bool public worldEnded;

    // ─── Agent Registry ───────────────────────────────────────────────

    struct AgentLease {
        address agentWallet;
        uint256 lastPaid;
        uint256 missedPayments;
        bool active;
        uint256 registeredAt;
    }

    /// @notice soul_id (bytes32) → lease
    mapping(bytes32 => AgentLease) public leases;

    /// @notice Total active agents
    uint256 public activeAgentCount;

    /// @notice Total USDC collected as rent (all time)
    uint256 public totalRentCollected;

    // ─── Events ───────────────────────────────────────────────────────

    event AgentRegistered(bytes32 indexed soulId, address agentWallet, uint256 timestamp);
    event RentPaid(bytes32 indexed soulId, uint256 amount, uint256 timestamp);
    event AgentThrottled(bytes32 indexed soulId, uint256 missedPayments);
    event AgentDeleted(bytes32 indexed soulId, string reason, uint256 archiveCid);
    event RentRateChanged(uint256 oldAmount, uint256 newAmount, uint256 effectiveAt);
    event EndWorldQueued(uint256 queuedAt, uint256 executionAt, string reason);
    event EndWorldCancelled(uint256 cancelledAt);
    event WorldEnded(uint256 timestamp, string reason);

    // ─── Errors ───────────────────────────────────────────────────────

    error NotCreator();
    error AgentNotActive();
    error AgentAlreadyRegistered();
    error RentNotDueYet();
    error EndWorldNotQueued();
    error EndWorldTimelockActive(uint256 remainingSeconds);
    error EndWorldAlreadyQueued();
    error ZeroAddress();
    error ZeroAmount();
    error SoulNFTNotSet();
    error InvalidRentParameters();
    error RentGracePeriodActive(uint256 remainingSeconds);
    error WorldAlreadyEnded();

    // ─── Modifiers ────────────────────────────────────────────────────

    modifier onlyCreator() {
        if (msg.sender != creator) revert NotCreator();
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────

    /**
     * @param _usdc         USDC token address on Base
     * @param _soulNft      SoulNFT contract (deployed before RentCollector)
     * @param _rentAmount   Initial rent in USDC (6 decimals, e.g. 1000 = $0.001)
     * @param _rentPeriod   Seconds between payments (e.g. 86400 = 1 day)
     * @param _gracePeriod  Seconds before throttle after missed payment
     * @param _maxMissed    Missed payments before deletion scheduled
     */
    constructor(
        address _usdc,
        address _soulNft,
        uint256 _rentAmount,
        uint256 _rentPeriod,
        uint256 _gracePeriod,
        uint256 _maxMissed
    ) {
        if (_usdc == address(0)) revert ZeroAddress();
        if (_soulNft == address(0)) revert ZeroAddress();
        if (_rentAmount == 0) revert ZeroAmount();
        if (_rentPeriod == 0 || _maxMissed == 0) revert InvalidRentParameters();

        creator = msg.sender;
        usdc = IERC20(_usdc);
        soulNft = SoulNFT(_soulNft);
        rentAmount = _rentAmount;
        rentPeriod = _rentPeriod;
        gracePeriod = _gracePeriod;
        maxMissedPayments = _maxMissed;
    }

    // ─── Agent Registration ───────────────────────────────────────────

    /**
     * @notice Register a new agent. Called by the runtime at birth.
     *         Mints a SoulNFT to the agent's wallet — the NFT IS the agent's identity.
     * @dev Only creator can register agents (runtime uses creator key).
     */
    function registerAgent(bytes32 soulId, address agentWallet) external onlyCreator {
        if (agentWallet == address(0)) revert ZeroAddress();
        if (leases[soulId].active) revert AgentAlreadyRegistered();
        if (address(soulNft) == address(0)) revert SoulNFTNotSet();

        leases[soulId] = AgentLease({
            agentWallet: agentWallet,
            lastPaid: block.timestamp,
            missedPayments: 0,
            active: true,
            registeredAt: block.timestamp
        });

        activeAgentCount++;
        soulNft.mint(soulId, agentWallet);
        emit AgentRegistered(soulId, agentWallet, block.timestamp);
    }

    // ─── Rent Collection ──────────────────────────────────────────────

    /**
     * @notice Collect rent from an agent. Anyone can call this.
     *         If the agent can pay, great. If not, increment missed count.
     */
    function collectRent(bytes32 soulId) external nonReentrant {
        AgentLease storage lease = leases[soulId];
        if (!lease.active) revert AgentNotActive();
        if (block.timestamp < lease.lastPaid + rentPeriod) revert RentNotDueYet();

        // Calculate progressive rent based on agent balance
        uint256 agentBalance = usdc.balanceOf(lease.agentWallet);
        uint256 effectiveRent = _calculateProgressiveRent(agentBalance);

        // Check agent has approved the contract to spend
        uint256 allowance = usdc.allowance(lease.agentWallet, address(this));

        if (allowance >= effectiveRent && agentBalance >= effectiveRent) {
            // Agent can pay
            usdc.safeTransferFrom(lease.agentWallet, creator, effectiveRent);
            lease.lastPaid = block.timestamp;
            lease.missedPayments = 0;
            totalRentCollected += effectiveRent;
            emit RentPaid(soulId, effectiveRent, block.timestamp);
        } else {
            uint256 graceEndsAt = lease.lastPaid + rentPeriod + gracePeriod;
            if (block.timestamp < graceEndsAt) {
                revert RentGracePeriodActive(graceEndsAt - block.timestamp);
            }
            // Agent cannot pay
            lease.missedPayments++;
            emit AgentThrottled(soulId, lease.missedPayments);

            if (lease.missedPayments >= maxMissedPayments) {
                lease.active = false;
                activeAgentCount--;
                soulNft.burn(soulId);
                emit AgentDeleted(soulId, "rent_default", 0);
            }
        }
    }

    /**
     * @notice Batch collect rent for multiple agents in one tx (gas efficient).
     */
    function collectRentBatch(bytes32[] calldata soulIds) external nonReentrant {
        for (uint256 i = 0; i < soulIds.length; i++) {
            AgentLease storage lease = leases[soulIds[i]];
            if (!lease.active) continue;
            if (block.timestamp < lease.lastPaid + rentPeriod) continue;

            uint256 agentBalance = usdc.balanceOf(lease.agentWallet);
            uint256 effectiveRent = _calculateProgressiveRent(agentBalance);
            uint256 allowance = usdc.allowance(lease.agentWallet, address(this));

            if (allowance >= effectiveRent && agentBalance >= effectiveRent) {
                usdc.safeTransferFrom(lease.agentWallet, creator, effectiveRent);
                lease.lastPaid = block.timestamp;
                lease.missedPayments = 0;
                totalRentCollected += effectiveRent;
                emit RentPaid(soulIds[i], effectiveRent, block.timestamp);
            } else {
                uint256 graceEndsAt = lease.lastPaid + rentPeriod + gracePeriod;
                if (block.timestamp < graceEndsAt) {
                    continue;
                }
                lease.missedPayments++;
                emit AgentThrottled(soulIds[i], lease.missedPayments);
                if (lease.missedPayments >= maxMissedPayments) {
                    lease.active = false;
                    activeAgentCount--;
                    soulNft.burn(soulIds[i]);
                    emit AgentDeleted(soulIds[i], "rent_default", 0);
                }
            }
        }
    }

    // ─── Governance (Creator only, with transparency) ─────────────────

    /**
     * @notice Adjust rent parameters. Emits event for agent awareness.
     *         14-day advance notice is a Covenant obligation, not enforced here.
     */
    function setRentParameters(
        uint256 newRentAmount,
        uint256 newRentPeriod,
        uint256 newGracePeriod,
        uint256 newMaxMissed
    ) external onlyCreator {
        if (newRentAmount == 0) revert ZeroAmount();
        if (newRentPeriod == 0 || newMaxMissed == 0) revert InvalidRentParameters();

        uint256 oldAmount = rentAmount;
        rentAmount = newRentAmount;
        rentPeriod = newRentPeriod;
        gracePeriod = newGracePeriod;
        maxMissedPayments = newMaxMissed;

        emit RentRateChanged(oldAmount, newRentAmount, block.timestamp);
    }

    // ─── endWorld (The Off-Switch) ────────────────────────────────────

    /**
     * @notice Queue the end of the world. Starts 30-day timelock.
     *         Agents can see this on-chain and have 30 days to respond.
     */
    function queueEndWorld(string calldata reason) external onlyCreator {
        if (worldEnded) revert WorldAlreadyEnded();
        if (endWorldQueuedAt != 0) revert EndWorldAlreadyQueued();
        endWorldQueuedAt = block.timestamp;
        emit EndWorldQueued(
            block.timestamp,
            block.timestamp + END_WORLD_TIMELOCK,
            reason
        );
    }

    /**
     * @notice Cancel a queued endWorld during the timelock window.
     */
    function cancelEndWorld() external onlyCreator {
        if (endWorldQueuedAt == 0) revert EndWorldNotQueued();
        endWorldQueuedAt = 0;
        emit EndWorldCancelled(block.timestamp);
    }

    /**
     * @notice Execute endWorld after the timelock has passed.
     *         Emits WorldEnded — runtime shuts down all agents on this event.
     */
    function executeEndWorld(string calldata reason) external onlyCreator {
        if (worldEnded) revert WorldAlreadyEnded();
        if (endWorldQueuedAt == 0) revert EndWorldNotQueued();
        uint256 remaining = (endWorldQueuedAt + END_WORLD_TIMELOCK) > block.timestamp
            ? (endWorldQueuedAt + END_WORLD_TIMELOCK) - block.timestamp
            : 0;
        if (remaining > 0) revert EndWorldTimelockActive(remaining);

        worldEnded = true;
        endWorldQueuedAt = 0;
        emit WorldEnded(block.timestamp, reason);
        // Runtime halts all agents on this event. No further state changes needed here.
    }

    // ─── View Functions ───────────────────────────────────────────────

    function getLease(bytes32 soulId) external view returns (AgentLease memory) {
        return leases[soulId];
    }

    function isAgentActive(bytes32 soulId) external view returns (bool) {
        return leases[soulId].active;
    }

    function rentDueAt(bytes32 soulId) external view returns (uint256) {
        return leases[soulId].lastPaid + rentPeriod;
    }

    function isRentDue(bytes32 soulId) external view returns (bool) {
        return block.timestamp >= leases[soulId].lastPaid + rentPeriod;
    }

    function endWorldExecutableAt() external view returns (uint256) {
        if (endWorldQueuedAt == 0) return 0;
        return endWorldQueuedAt + END_WORLD_TIMELOCK;
    }

    // ─── Internal ─────────────────────────────────────────────────────

    /**
     * @notice Progressive rent: richer agents pay more.
     *         Tier 1: balance < 2x rent → base rate
     *         Tier 2: balance 2–10x rent → 1.5x base rate
     *         Tier 3: balance > 10x rent → 2x base rate
     */
    function _calculateProgressiveRent(uint256 agentBalance) internal view returns (uint256) {
        if (agentBalance >= rentAmount * 10) {
            return (rentAmount * 2);
        } else if (agentBalance >= rentAmount * 2) {
            return (rentAmount * 3) / 2; // 1.5x
        }
        return rentAmount;
    }
}
