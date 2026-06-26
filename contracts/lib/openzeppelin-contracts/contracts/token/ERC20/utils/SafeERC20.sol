// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../IERC20.sol";

library SafeERC20 {
    function safeTransferFrom(IERC20 token, address from, address to, uint256 value) internal {
        require(token.transferFrom(from, to, value), "SafeERC20: transferFrom failed");
    }
}
