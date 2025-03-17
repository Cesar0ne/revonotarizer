# revonotarizer
Notarevorizer automates document notarization on the Revo blockchain using Python. It monitors a folder for new files, waits until they are stable, computes their SHA‑256 hash, and notarizes them via Revo CLI. It generates PDF receipts and logs events with rotation, plus notarizes random cowsay phrases.

Notarevorizer is a Python-based automation tool for notarizing documents on the Revo blockchain. The script continuously monitors a designated folder, waits until each file is fully written, computes its SHA‑256 hash, and notarizes the file by sending a transaction via the Revo CLI with a promotional message. It also generates a PDF receipt that summarizes key details—such as file name, size, timestamp, and transaction output—and logs all events with automatic log rotation.

Revo is a public, decentralized blockchain that combines high performance, scalability, and energy efficiency through its innovative PoS v3 consensus algorithm. Fully EVM compatible and designed to support enterprise-grade applications, Revo offers features like dynamic block sizing, sidechains, decentralized storage, and on-chain governance, making it ideal for secure notarization, supply chain traceability, and much more.

This side project is released under the MIT license and is part of the broader Revo ecosystem. For more details on the Revo blockchain, visit revo.network and explore the larger project on GitHub at github.com/revolutionchain/revo.

