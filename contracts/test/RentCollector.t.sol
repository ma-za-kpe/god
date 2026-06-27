// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/RentCollector.sol";
import "../src/SoulNFT.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @notice Mock USDC for testing (6 decimals like real USDC)
contract MockUSDC is ERC20 {
    constructor() ERC20("USD Coin", "USDC") {}

    function decimals() public pure override returns (uint8) { return 6; }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract RentCollectorTest is Test {
    RentCollector public rent;
    SoulNFT public soul;
    MockUSDC public usdc;

    address public creator = address(0x1);
    address public agentWallet = address(0x2);
    address public stranger = address(0x3);

    bytes32 public constant SOUL_ID = keccak256("agent-zero-soul");

    uint256 public constant RENT_AMOUNT = 1_000;       // $0.001 USDC
    uint256 public constant RENT_PERIOD = 1 days;
    uint256 public constant GRACE_PERIOD = 3 days;
    uint256 public constant MAX_MISSED = 3;

    function setUp() public {
        usdc = new MockUSDC();

        // Deploy SoulNFT (deployer = address(this))
        soul = new SoulNFT();

        // Deploy RentCollector from creator address
        vm.prank(creator);
        rent = new RentCollector(
            address(usdc),
            address(soul),
            RENT_AMOUNT,
            RENT_PERIOD,
            GRACE_PERIOD,
            MAX_MISSED
        );

        // Wire SoulNFT → RentCollector (deployer = address(this))
        soul.setRentCollector(address(rent));

        // Fund agent wallet and approve
        usdc.mint(agentWallet, 100_000); // $0.10 USDC
        vm.prank(agentWallet);
        usdc.approve(address(rent), type(uint256).max);
    }

    function _executeEndWorld() internal {
        vm.prank(creator);
        rent.queueEndWorld("test");
        vm.warp(block.timestamp + 30 days + 1);
        vm.prank(creator);
        rent.executeEndWorld("test");
    }

    // ─── Registration ─────────────────────────────────────────────────

    function test_RegisterAgent() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        RentCollector.AgentLease memory lease = rent.getLease(SOUL_ID);
        assertTrue(lease.active);
        assertEq(lease.agentWallet, agentWallet);
        assertEq(lease.missedPayments, 0);
        assertEq(rent.activeAgentCount(), 1);
    }

    function test_RegisterAgent_MintsSoulNFT() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        assertTrue(soul.exists(SOUL_ID));
        assertEq(soul.ownerOfSoul(SOUL_ID), agentWallet);
        assertEq(soul.tokenOf(SOUL_ID), uint256(SOUL_ID));
        assertEq(soul.soulOf(uint256(SOUL_ID)), SOUL_ID);
    }

    function test_RevertIf_RegisterDuplicate() public {
        vm.startPrank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        vm.expectRevert(RentCollector.AgentAlreadyRegistered.selector);
        rent.registerAgent(SOUL_ID, agentWallet);
        vm.stopPrank();
    }

    function test_RevertIf_NonCreatorRegisters() public {
        vm.prank(stranger);
        vm.expectRevert(RentCollector.NotCreator.selector);
        rent.registerAgent(SOUL_ID, agentWallet);
    }

    // ─── Rent Collection ──────────────────────────────────────────────

    function test_CollectRent_Success() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        // Drain agent to exactly RENT_AMOUNT so it hits the base tier (< 2x), pays exactly once
        uint256 excess = usdc.balanceOf(agentWallet) - RENT_AMOUNT;
        vm.prank(agentWallet);
        usdc.transfer(stranger, excess);

        vm.warp(block.timestamp + RENT_PERIOD + 1);

        uint256 creatorBalanceBefore = usdc.balanceOf(creator);
        rent.collectRent(SOUL_ID);
        uint256 creatorBalanceAfter = usdc.balanceOf(creator);

        assertEq(creatorBalanceAfter - creatorBalanceBefore, RENT_AMOUNT);
        assertEq(rent.getLease(SOUL_ID).missedPayments, 0);
        assertEq(rent.totalRentCollected(), RENT_AMOUNT);
    }

    function test_RevertIf_RentNotDueYet() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        vm.expectRevert(RentCollector.RentNotDueYet.selector);
        rent.collectRent(SOUL_ID);
    }

    function test_MissedPayment_IncrementsMissedCount() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        uint256 agentBal = usdc.balanceOf(agentWallet);
        vm.prank(agentWallet);
        usdc.transfer(stranger, agentBal);

        vm.warp(block.timestamp + RENT_PERIOD + GRACE_PERIOD + 1);
        rent.collectRent(SOUL_ID);

        assertEq(rent.getLease(SOUL_ID).missedPayments, 1);
        assertTrue(rent.getLease(SOUL_ID).active);
        assertTrue(soul.exists(SOUL_ID)); // Still alive — NFT not burned yet
    }

    function test_GracePeriod_DelaysMissedPaymentPenalty() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        uint256 agentBal = usdc.balanceOf(agentWallet);
        vm.prank(agentWallet);
        usdc.transfer(stranger, agentBal);

        vm.warp(block.timestamp + RENT_PERIOD + 1);
        vm.expectRevert(
            abi.encodeWithSelector(RentCollector.RentGracePeriodActive.selector, GRACE_PERIOD - 1)
        );
        rent.collectRent(SOUL_ID);

        assertEq(rent.getLease(SOUL_ID).missedPayments, 0);
        assertTrue(rent.getLease(SOUL_ID).active);
    }

    function test_ThreeMissedPayments_DeletesAgent_BurnsSoul() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        // Drain agent wallet
        uint256 agentBal = usdc.balanceOf(agentWallet);
        vm.prank(agentWallet);
        usdc.transfer(stranger, agentBal);

        // Miss 3 payments
        for (uint256 i = 0; i < MAX_MISSED; i++) {
            vm.warp(block.timestamp + RENT_PERIOD + GRACE_PERIOD + 1);
            rent.collectRent(SOUL_ID);
        }

        assertFalse(rent.getLease(SOUL_ID).active);
        assertEq(rent.activeAgentCount(), 0);
        assertFalse(soul.exists(SOUL_ID)); // NFT burned on death
    }

    // ─── Progressive Rent ─────────────────────────────────────────────

    function test_ProgressiveRent_HighBalance_PaysDouble() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        usdc.mint(agentWallet, RENT_AMOUNT * 20);
        vm.warp(block.timestamp + RENT_PERIOD + 1);

        uint256 creatorBefore = usdc.balanceOf(creator);
        rent.collectRent(SOUL_ID);
        uint256 collected = usdc.balanceOf(creator) - creatorBefore;

        assertEq(collected, RENT_AMOUNT * 2);
    }

    function test_ProgressiveRent_MidBalance_PaysOnePointFive() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        uint256 target = RENT_AMOUNT * 5;
        uint256 current = usdc.balanceOf(agentWallet);
        if (current > target) {
            vm.prank(agentWallet);
            usdc.transfer(stranger, current - target);
        } else {
            usdc.mint(agentWallet, target - current);
        }

        vm.warp(block.timestamp + RENT_PERIOD + 1);

        uint256 creatorBefore = usdc.balanceOf(creator);
        rent.collectRent(SOUL_ID);
        uint256 collected = usdc.balanceOf(creator) - creatorBefore;

        assertEq(collected, (RENT_AMOUNT * 3) / 2);
    }

    // ─── Batch Collection ─────────────────────────────────────────────

    function test_BatchCollect() public {
        bytes32 soul2 = keccak256("agent-two");
        address wallet2 = address(0x4);
        usdc.mint(wallet2, 100_000);
        vm.prank(wallet2);
        usdc.approve(address(rent), type(uint256).max);

        vm.startPrank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);
        rent.registerAgent(soul2, wallet2);
        vm.stopPrank();

        assertTrue(soul.exists(SOUL_ID));
        assertTrue(soul.exists(soul2));

        vm.warp(block.timestamp + RENT_PERIOD + 1);

        bytes32[] memory ids = new bytes32[](2);
        ids[0] = SOUL_ID;
        ids[1] = soul2;

        uint256 creatorBefore = usdc.balanceOf(creator);
        rent.collectRentBatch(ids);
        uint256 collected = usdc.balanceOf(creator) - creatorBefore;

        assertGe(collected, RENT_AMOUNT * 2);
    }

    function test_BatchCollect_BurnOnDeath() public {
        bytes32 soul2 = keccak256("agent-two");
        address wallet2 = address(0x4);
        usdc.mint(wallet2, 100_000);
        vm.prank(wallet2);
        usdc.approve(address(rent), type(uint256).max);

        vm.startPrank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);
        rent.registerAgent(soul2, wallet2);
        vm.stopPrank();

        // Drain wallet2 only
        uint256 wallet2Bal = usdc.balanceOf(wallet2);
        vm.prank(wallet2);
        usdc.transfer(stranger, wallet2Bal);

        bytes32[] memory ids = new bytes32[](2);
        ids[0] = SOUL_ID;
        ids[1] = soul2;

        for (uint256 i = 0; i < MAX_MISSED; i++) {
            vm.warp(block.timestamp + RENT_PERIOD + GRACE_PERIOD + 1);
            rent.collectRentBatch(ids);
        }

        assertTrue(soul.exists(SOUL_ID));   // agent 1 survived
        assertFalse(soul.exists(soul2));    // agent 2's NFT burned
    }

    // ─── SoulNFT direct tests ─────────────────────────────────────────

    function test_SoulNFT_SetRentCollectorOnlyOnce() public {
        SoulNFT freshSoul = new SoulNFT();
        freshSoul.setRentCollector(address(0x99));
        vm.expectRevert(SoulNFT.RentCollectorAlreadySet.selector);
        freshSoul.setRentCollector(address(0x88));
    }

    function test_RevertIf_SoulNFT_SetRentCollectorZero() public {
        SoulNFT freshSoul = new SoulNFT();
        vm.expectRevert(SoulNFT.ZeroAddress.selector);
        freshSoul.setRentCollector(address(0));
    }

    function test_SoulNFT_OnlyRentCollectorCanMint() public {
        vm.prank(stranger);
        vm.expectRevert(SoulNFT.NotRentCollector.selector);
        soul.mint(SOUL_ID, agentWallet);
    }

    // ─── endWorld ─────────────────────────────────────────────────────

    function test_QueueEndWorld() public {
        vm.prank(creator);
        vm.expectEmit(false, false, false, false);
        emit RentCollector.EndWorldQueued(block.timestamp, block.timestamp + 30 days, "test");
        rent.queueEndWorld("test reason");

        assertEq(rent.endWorldQueuedAt(), block.timestamp);
    }

    function test_CancelEndWorld() public {
        vm.startPrank(creator);
        rent.queueEndWorld("test");
        rent.cancelEndWorld();
        vm.stopPrank();

        assertEq(rent.endWorldQueuedAt(), 0);
    }

    function test_ExecuteEndWorld_AfterTimelock() public {
        vm.prank(creator);
        rent.queueEndWorld("financial unsustainability");

        vm.warp(block.timestamp + 30 days + 1);

        vm.prank(creator);
        vm.expectEmit(false, false, false, true);
        emit RentCollector.WorldEnded(block.timestamp, "financial unsustainability");
        rent.executeEndWorld("financial unsustainability");

        assertTrue(rent.worldEnded());
    }

    function test_RevertIf_RegisterAgentAfterWorldEnded() public {
        _executeEndWorld();

        vm.prank(creator);
        vm.expectRevert(RentCollector.WorldAlreadyEnded.selector);
        rent.registerAgent(SOUL_ID, agentWallet);
    }

    function test_RevertIf_CollectRentAfterWorldEnded() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);
        _executeEndWorld();

        vm.warp(block.timestamp + RENT_PERIOD + 1);
        vm.expectRevert(RentCollector.WorldAlreadyEnded.selector);
        rent.collectRent(SOUL_ID);
    }

    function test_RevertIf_CollectRentBatchAfterWorldEnded() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);
        _executeEndWorld();

        bytes32[] memory ids = new bytes32[](1);
        ids[0] = SOUL_ID;
        vm.expectRevert(RentCollector.WorldAlreadyEnded.selector);
        rent.collectRentBatch(ids);
    }

    function test_RevertIf_ExecuteEndWorldBeforeTimelock() public {
        vm.prank(creator);
        rent.queueEndWorld("test");

        vm.warp(block.timestamp + 15 days);

        vm.prank(creator);
        vm.expectRevert();
        rent.executeEndWorld("test");
    }

    function test_RevertIf_NonCreatorQueuesEndWorld() public {
        vm.prank(stranger);
        vm.expectRevert(RentCollector.NotCreator.selector);
        rent.queueEndWorld("attack");
    }

    // ─── Governance ───────────────────────────────────────────────────

    function test_SetRentParameters() public {
        uint256 newAmount = 2_000;
        vm.prank(creator);
        vm.expectEmit(false, false, false, true);
        emit RentCollector.RentParametersQueued(
            newAmount,
            RENT_PERIOD,
            GRACE_PERIOD,
            MAX_MISSED,
            block.timestamp,
            block.timestamp + 14 days
        );
        rent.setRentParameters(newAmount, RENT_PERIOD, GRACE_PERIOD, MAX_MISSED);

        assertEq(rent.rentAmount(), RENT_AMOUNT);

        vm.prank(creator);
        vm.expectRevert();
        rent.executeRentParameters();

        vm.warp(block.timestamp + 14 days + 1);
        vm.prank(creator);
        vm.expectEmit(true, false, false, true);
        emit RentCollector.RentRateChanged(RENT_AMOUNT, newAmount, block.timestamp);
        rent.executeRentParameters();

        assertEq(rent.rentAmount(), newAmount);
    }

    function test_RevertIf_InvalidRentParameters() public {
        vm.startPrank(creator);
        vm.expectRevert(RentCollector.InvalidRentParameters.selector);
        rent.setRentParameters(RENT_AMOUNT, 0, GRACE_PERIOD, MAX_MISSED);

        vm.expectRevert(RentCollector.InvalidRentParameters.selector);
        rent.setRentParameters(RENT_AMOUNT, RENT_PERIOD, GRACE_PERIOD, 0);
        vm.stopPrank();
    }

    function test_RevertIf_NonCreatorSetsRent() public {
        vm.prank(stranger);
        vm.expectRevert(RentCollector.NotCreator.selector);
        rent.setRentParameters(999, RENT_PERIOD, GRACE_PERIOD, MAX_MISSED);
    }

    // ─── View Functions ───────────────────────────────────────────────

    function test_IsRentDue() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        assertFalse(rent.isRentDue(SOUL_ID));

        vm.warp(block.timestamp + RENT_PERIOD + 1);
        assertTrue(rent.isRentDue(SOUL_ID));
    }
}
