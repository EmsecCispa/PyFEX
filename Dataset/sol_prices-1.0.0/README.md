# DEX Price Fetching Library for Ethereum and Solana

This Python library provides utilities to fetch token prices from decentralized exchanges (DEXs) across Ethereum and Solana networks. It uses Web3.py for Ethereum and the Solders library for Solana, along with other utilities to interact with DEXs like Uniswap, Sushiswap, Pancakeswap (Ethereum), and Serum (Solana).

## Features

- **Ethereum (Uniswap, Sushiswap, Pancakeswap)**: 
  - Fetch prices of tokens.
  - Get pair address and reserves for token pairs.
  - Retrieve token symbol, total supply, and decimals.
  - Get the current block number and gas price.
  
- **Solana (Serum)**:
  - Fetch prices from Serum DEX on Solana.
  - Get the token balance of any Solana address.
  - Retrieve Solana transaction fees and account balances.

- **Utilities**:
  - Fetch the total supply of ERC-20 tokens.
  - Retrieve Solana transaction statuses.
  - Convert Base58 addresses to Solana public keys.

## Requirements

- Python 3.x
- Install required libraries via `pip`:
