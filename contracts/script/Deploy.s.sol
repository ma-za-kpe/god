// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "../src/SoulNFT.sol";
import "../src/RentCollector.sol";

/// Minimal USDC stand-in for Anvil local dev.
/// Only deployed when USDC_ADDRESS env var is not set.
contract MockUSDC is ERC20 {
    constructor() ERC20("USD Coin (Dev)", "USDC") {
        _mint(msg.sender, 10_000_000 * 1e6); // 10M USDC to deployer
    }

    function decimals() public pure override returns (uint8) { return 6; }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address usdcAddress = vm.envOr("USDC_ADDRESS", address(0));

        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy MockUSDC if not provided
        if (usdcAddress == address(0)) {
            MockUSDC mockUsdc = new MockUSDC();
            usdcAddress = address(mockUsdc);
            console.log("MockUSDC deployed:", usdcAddress);
        }

        // 2. Deploy SoulNFT (rentCollector wired in step 4)
        SoulNFT soul = new SoulNFT();
        console.log("SoulNFT deployed:  ", address(soul));

        // 3. Deploy RentCollector
        //    rentAmount: 1000 = 0.001 USDC (6 decimals)
        //    rentPeriod: 300s  = 5 minutes (dev-speed; 1 day in prod)
        //    gracePeriod: 180s = 3 minutes
        //    maxMissedPayments: 3
        RentCollector rent = new RentCollector(
            usdcAddress,
            address(soul),
            1_000,
            300,
            180,
            3
        );
        console.log("RentCollector deployed:", address(rent));

        // 4. Wire SoulNFT → RentCollector (one-time, set-once)
        soul.setRentCollector(address(rent));
        console.log("SoulNFT wired to RentCollector");

        vm.stopBroadcast();

        console.log("===========================================");
        console.log("Add these to .env.local:");
        console.log("RENT_COLLECTOR_ADDRESS=", vm.toString(address(rent)));
        console.log("SOUL_NFT_ADDRESS=       ", vm.toString(address(soul)));
        console.log("USDC_ADDRESS=           ", vm.toString(usdcAddress));
        console.log("===========================================");
    }
}
