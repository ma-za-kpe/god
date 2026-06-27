// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

/**
 * @title SoulNFT
 * @notice Each agent is an NFT. tokenId = uint256(soulId).
 *         Minted at birth, burned at death. Only RentCollector can mint/burn.
 *
 *         Deployment order (circular dep resolved via set-once pattern):
 *           1. Deploy SoulNFT (rentCollector = address(0))
 *           2. Deploy RentCollector(soulNft = address(soulNft))
 *           3. soulNft.setRentCollector(address(rent))  ← one-time call
 *
 *         ERC-6551 readiness: when the token-bound account registry is
 *         available, each token's deterministic TBA replaces the current EOA.
 *         The soul_id ↔ tokenId bijection ensures zero-migration continuity.
 */
contract SoulNFT is ERC721 {

    address public rentCollector;
    address public immutable deployer;

    error NotRentCollector();
    error NotDeployer();
    error RentCollectorAlreadySet();
    error ZeroAddress();
    error SoulAlreadyMinted(bytes32 soulId);
    error SoulNotFound(bytes32 soulId);

    modifier onlyRentCollector() {
        if (msg.sender != rentCollector) revert NotRentCollector();
        _;
    }

    constructor() ERC721("GOD Soul", "SOUL") {
        deployer = msg.sender;
    }

    /**
     * @notice Wire up the RentCollector after it is deployed. One-time only.
     */
    function setRentCollector(address _rentCollector) external {
        if (msg.sender != deployer) revert NotDeployer();
        if (_rentCollector == address(0)) revert ZeroAddress();
        if (rentCollector != address(0)) revert RentCollectorAlreadySet();
        rentCollector = _rentCollector;
    }

    // ─── Mint / Burn ──────────────────────────────────────────────────

    /**
     * @notice Mint a soul NFT at agent birth. Called by RentCollector.registerAgent.
     * @param soulId  The agent's permanent soul_id (bytes32).
     * @param to      The EOA that initially holds the NFT (agent operational wallet).
     */
    function mint(bytes32 soulId, address to) external onlyRentCollector {
        uint256 tokenId = uint256(soulId);
        if (_ownerOf(tokenId) != address(0)) revert SoulAlreadyMinted(soulId);
        _mint(to, tokenId);
    }

    /**
     * @notice Burn a soul NFT at agent death. Called by RentCollector on eviction.
     * @param soulId  The soul_id of the dying agent.
     */
    function burn(bytes32 soulId) external onlyRentCollector {
        uint256 tokenId = uint256(soulId);
        if (_ownerOf(tokenId) == address(0)) revert SoulNotFound(soulId);
        _burn(tokenId);
    }

    // ─── View ─────────────────────────────────────────────────────────

    function tokenOf(bytes32 soulId) external pure returns (uint256) {
        return uint256(soulId);
    }

    function soulOf(uint256 tokenId) external pure returns (bytes32) {
        return bytes32(tokenId);
    }

    function exists(bytes32 soulId) external view returns (bool) {
        return _ownerOf(uint256(soulId)) != address(0);
    }

    function ownerOfSoul(bytes32 soulId) external view returns (address) {
        return _ownerOf(uint256(soulId));
    }

    /**
     * @notice Pre-compute the ERC-6551 TBA address for a soul.
     *         Once the registry is deployed to the target network, this
     *         is the agent's canonical wallet address.
     *
     * @param registry        ERC-6551 registry (0x000000006551c19487814612e58FE06813775758 on mainnet).
     * @param implementation  TBA implementation contract address.
     * @param chainId         Chain ID (8453 = Base mainnet, 84532 = local Anvil).
     */
    function computeTBAAddress(
        address registry,
        address implementation,
        uint256 chainId,
        bytes32 soulId
    ) external view returns (address) {
        uint256 tokenId = uint256(soulId);
        bytes32 salt = keccak256(abi.encode(chainId, address(this), tokenId));
        bytes memory creationCode = abi.encodePacked(
            hex"3d60ad80600a3d3981f3363d3d373d3d3d363d73",
            implementation,
            hex"5af43d82803e903d91602b57fd5bf3"
        );
        bytes32 codeHash = keccak256(creationCode);
        return address(uint160(uint256(keccak256(abi.encodePacked(
            bytes1(0xff), registry, salt, codeHash
        )))));
    }
}
