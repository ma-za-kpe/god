// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title AgentToken — Deployable ERC-20 for GOD Project agents
/// @dev Deployed by runtime/src/token_factory.py on behalf of agent wallets.
///      Immutable once deployed — no upgrades, no proxy.
contract AgentToken is ERC20 {
    uint8 private _decimals;

    /// Hard cap: 1 billion tokens at 18 decimals
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10 ** 18;

    /// Transfer tax in basis points (0–1000, i.e. 0%–10%)
    uint16 public transferTaxBps;

    /// Destination for collected tax; address(0) = burn
    address public taxRecipient;

    event TokenDeployed(
        address indexed owner,
        string name,
        string symbol,
        uint256 initialSupply
    );

    constructor(
        string memory name_,
        string memory symbol_,
        uint8 decimals_,
        uint256 initialSupply,
        uint16 _transferTaxBps,
        address _taxRecipient,
        address owner_
    ) ERC20(name_, symbol_) {
        require(owner_ != address(0), "Owner is zero");
        require(initialSupply <= MAX_SUPPLY, "Supply exceeds max");
        require(_transferTaxBps <= 1000, "Tax too high (max 10%)");
        _decimals = decimals_;
        transferTaxBps = _transferTaxBps;
        taxRecipient = _taxRecipient;
        _mint(owner_, initialSupply);
        emit TokenDeployed(owner_, name_, symbol_, initialSupply);
    }

    function decimals() public view override returns (uint8) {
        return _decimals;
    }

    /// @dev Hook — applies transfer tax before every transfer (except mint/burn)
    function _update(
        address from,
        address to,
        uint256 value
    ) internal override {
        if (transferTaxBps > 0 && from != address(0) && to != address(0)) {
            uint256 tax = (value * transferTaxBps) / 10000;
            uint256 net = value - tax;

            if (taxRecipient == address(0)) {
                // Burn the tax portion
                super._update(from, address(0), tax);
            } else {
                super._update(from, taxRecipient, tax);
            }
            super._update(from, to, net);
        } else {
            super._update(from, to, value);
        }
    }

}
