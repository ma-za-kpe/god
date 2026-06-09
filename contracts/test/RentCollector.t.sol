// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/RentCollector.sol";
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

        vm.prank(creator);
        rent = new RentCollector(
            address(usdc),
            RENT_AMOUNT,
            RENT_PERIOD,
            GRACE_PERIOD,
            MAX_MISSED
        );

        // Fund agent wallet and approve
        usdc.mint(agentWallet, 100_000); // $0.10 USDC
        vm.prank(agentWallet);
        usdc.approve(address(rent), type(uint256).max);
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

        // Advance time past rent period
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

        // Remove agent's funds so they can't pay
        vm.prank(agentWallet);
        usdc.transfer(stranger, usdc.balanceOf(agentWallet));

        vm.warp(block.timestamp + RENT_PERIOD + 1);
        rent.collectRent(SOUL_ID);

        assertEq(rent.getLease(SOUL_ID).missedPayments, 1);
        assertTrue(rent.getLease(SOUL_ID).active); // Still alive
    }

    function test_ThreeMissedPayments_DeletesAgent() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        // Drain agent wallet
        vm.prank(agentWallet);
        usdc.transfer(stranger, usdc.balanceOf(agentWallet));

        // Miss 3 payments
        for (uint256 i = 0; i < MAX_MISSED; i++) {
            vm.warp(block.timestamp + RENT_PERIOD + 1);
            rent.collectRent(SOUL_ID);
        }

        assertFalse(rent.getLease(SOUL_ID).active);
        assertEq(rent.activeAgentCount(), 0);
    }

    // ─── Progressive Rent ─────────────────────────────────────────────

    function test_ProgressiveRent_HighBalance_PaysDouble() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        // Give agent a high balance (>10x rent)
        usdc.mint(agentWallet, RENT_AMOUNT * 20);

        vm.warp(block.timestamp + RENT_PERIOD + 1);

        uint256 creatorBefore = usdc.balanceOf(creator);
        rent.collectRent(SOUL_ID);
        uint256 collected = usdc.balanceOf(creator) - creatorBefore;

        assertEq(collected, RENT_AMOUNT * 2); // 2x rate
    }

    function test_ProgressiveRent_MidBalance_PaysOnePointFive() public {
        vm.prank(creator);
        rent.registerAgent(SOUL_ID, agentWallet);

        // Give agent 5x rent balance (in the 2–10x tier)
        // Reset to exactly 5x rent
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

        assertEq(collected, (RENT_AMOUNT * 3) / 2); // 1.5x rate
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

        vm.warp(block.timestamp + RENT_PERIOD + 1);

        bytes32[] memory ids = new bytes32[](2);
        ids[0] = SOUL_ID;
        ids[1] = soul2;

        uint256 creatorBefore = usdc.balanceOf(creator);
        rent.collectRentBatch(ids);
        uint256 collected = usdc.balanceOf(creator) - creatorBefore;

        assertGe(collected, RENT_AMOUNT * 2); // at least 2x base (could be progressive)
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
    }

    function test_RevertIf_ExecuteEndWorldBeforeTimelock() public {
        vm.prank(creator);
        rent.queueEndWorld("test");

        vm.warp(block.timestamp + 15 days); // Only half the timelock

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
        vm.expectEmit(true, false, false, true);
        emit RentCollector.RentRateChanged(RENT_AMOUNT, newAmount, block.timestamp);
        rent.setRentParameters(newAmount, RENT_PERIOD, GRACE_PERIOD, MAX_MISSED);

        assertEq(rent.rentAmount(), newAmount);
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
