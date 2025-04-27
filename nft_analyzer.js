const ethers = require('ethers');
const fs = require('fs');
const path = require('path');
const createCsvWriter = require('csv-writer').createObjectCsvWriter;
const dotenv = require('dotenv');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

// Load environment variables
dotenv.config();

// Constants
const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";
const TRANSFER_EVENT_SIGNATURE = "Transfer(address,address,uint256)";

// RPC endpoints from .env
const RPC_ENDPOINTS = [
  process.env.ALCHEMY_RPC,
  process.env.INFURA_RPC
].filter(Boolean); // Filter out undefined or empty values

/**
 * Set up directory structure for organized output
 * @param {string} contractAddress - The NFT contract address
 * @returns {Object} Object containing paths to different directories
 */
function setupDirectories(contractAddress) {
    // Create a timestamp for the run
    const timestamp = new Date().toISOString().replace(/[:.]/g, '').replace('T', '_').slice(0, 17);
    
    // Create main output directory with contract as name
    const contractShort = contractAddress.slice(0, 10); // First 10 chars of contract address
    const outputDir = `output_${contractShort}_${timestamp}`;
    
    // Create subdirectories
    const dirs = {
        main: outputDir,
        logs: path.join(outputDir, 'logs'),
        data: path.join(outputDir, 'data'),
        stats: path.join(outputDir, 'stats')
    };
    
    // Create all directories
    Object.values(dirs).forEach(dir => {
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
    });
    
    return dirs;
}

/**
 * Set up logging to both file and console
 * @param {string} logDir - Directory for log files
 * @returns {Object} Logger object
 */
function setupLogging(logDir) {
    const logFile = path.join(logDir, 'nft_analyzer.log');
    const logStream = fs.createWriteStream(logFile, { flags: 'a' });
    
    // Simple logger that writes to both file and console
    const logger = {
        info: (message) => {
            const logMessage = `[INFO] ${new Date().toISOString()} - ${message}`;
            console.log(message);
            logStream.write(logMessage + '\n');
        },
        warning: (message) => {
            const logMessage = `[WARNING] ${new Date().toISOString()} - ${message}`;
            console.warn(message);
            logStream.write(logMessage + '\n');
        },
        error: (message, error) => {
            const logMessage = `[ERROR] ${new Date().toISOString()} - ${message}${error ? ': ' + error.stack : ''}`;
            console.error(message);
            if (error) console.error(error);
            logStream.write(logMessage + '\n');
        }
    };
    
    return logger;
}

/**
 * Attempts to create an Ethers provider using various endpoints
 * @param {Object} logger - Logger object
 * @returns {ethers.JsonRpcProvider} A connected Ethers provider
 */
async function getFallbackProvider(logger) {
    for (const endpoint of RPC_ENDPOINTS) {
        try {
            // Using ethers v6 syntax
            const provider = new ethers.JsonRpcProvider(endpoint);
            // Test connection by fetching block number
            await provider.getBlockNumber();
            logger.info(`Connected to Ethereum node at ${endpoint.slice(0, 30)}...`);
            return provider;
        } catch (e) {
            logger.warning(`Failed to connect to ${endpoint.slice(0, 30)}... - ${e.message}`);
        }
    }
    throw new Error("Could not connect to any RPC endpoint");
}

/**
 * Get block timestamp for a given block number
 * @param {ethers.providers.Provider} provider - Ethers provider
 * @param {number} blockNumber - Block number
 * @returns {Promise<string>} Formatted date string
 */
async function getBlockTimestamp(provider, blockNumber) {
    const block = await provider.getBlock(blockNumber);
    return new Date(block.timestamp * 1000).toISOString().split('T')[0]; // YYYY-MM-DD
}

/**
 * Fetch all Transfer events from a contract
 * @param {ethers.JsonRpcProvider} provider - Ethers provider
 * @param {string} contractAddress - Contract address to fetch logs from
 * @param {Object} options - Options object with start/end blocks and batch size
 * @param {Object} logger - Logger object
 * @returns {Promise<Array>} Array of log objects
 */
async function fetchTransferLogs(provider, contractAddress, options, logger) {
    const {
        startBlock = 0,
        endBlock = 'latest',
        batchSize = 10000
    } = options;
    
    let finalEndBlock = endBlock;
    if (endBlock === 'latest') {
        finalEndBlock = await provider.getBlockNumber();
    }
    
    // Transfer event signature (topic0)
    const transferEventSignature = ethers.id("Transfer(address,address,uint256)");
    
    let allLogs = [];
    let currentStart = startBlock;
    
    logger.info(`Fetching logs from block ${startBlock} to ${finalEndBlock}`);
    
    while (currentStart <= finalEndBlock) {
        const currentEnd = Math.min(currentStart + batchSize - 1, finalEndBlock);
        logger.info(`Fetching batch: ${currentStart} to ${currentEnd}`);
        
        try {
            const logs = await provider.getLogs({
                fromBlock: currentStart,
                toBlock: currentEnd,
                address: contractAddress,
                topics: [transferEventSignature]
            });
            
            allLogs = allLogs.concat(logs);
            currentStart = currentEnd + 1;
        } catch (e) {
            const errorMsg = e.message.toLowerCase();
            
            if (errorMsg.includes("rate limit") || errorMsg.includes("429") || errorMsg.includes("too many requests")) {
                logger.warning(`Rate limit hit. Trying a different provider or reducing batch size.`);
                
                // Try with a different provider
                try {
                    provider = await getFallbackProvider(logger);
                    logger.info(`Switched to a different provider. Retrying...`);
                    continue;
                } catch (providerError) {
                    // If switching providers didn't work, reduce batch size
                    options.batchSize = Math.max(100, Math.floor(batchSize / 2));
                    logger.info(`Reducing batch size to ${options.batchSize} and retrying...`);
                    await new Promise(resolve => setTimeout(resolve, 2000)); // Add a delay
                    continue;
                }
            } else {
                // Other error, just raise it
                logger.error(`Error fetching logs: ${e.message}`, e);
                throw e;
            }
        }
    }
    
    return allLogs;
}

/**
 * Decode a Transfer event log into a structured object
 * @param {Object} log - The log object from ethers
 * @returns {Object} Structured transaction data
 */
function decodeTransferLog(log) {
    // Decode the log data
    const topics = log.topics;
    
    // In ethers v6, we need to convert these to strings first
    const fromTopic = topics[1];
    const toTopic = topics[2];
    
    // Extract the address from the last 20 bytes of the topic
    const fromAddress = `0x${fromTopic.substring(26)}`;
    const toAddress = `0x${toTopic.substring(26)}`;
    
    let tokenId;
    if (log.data === '0x') {
        // If data is empty, token ID is in topics[3]
        tokenId = ethers.toBigInt(topics[3]).toString();
    } else {
        // Otherwise, it's in the data field
        tokenId = ethers.toBigInt(log.data).toString();
    }
    
    return {
        txHash: log.transactionHash,
        block: log.blockNumber,
        from: ethers.getAddress(fromAddress), // Normalize address format
        to: ethers.getAddress(toAddress),
        tokenId: tokenId,
        type: ethers.getAddress(fromAddress) === ZERO_ADDRESS ? 'MINT' : 'TRANSFER'
    };
}

/**
 * Analyze transfer data and save statistics
 * @param {Array} transactions - Array of decoded transfer logs
 * @param {Object} outputDirs - Object containing output directory paths
 * @param {Object} logger - Logger object
 */
function analyzeTransfers(transactions, outputDirs, logger) {
    // Basic statistics
    const totalTransactions = transactions.length;
    const totalMints = transactions.filter(tx => tx.type === 'MINT').length;
    const totalTransfers = transactions.filter(tx => tx.type === 'TRANSFER').length;
    
    // Top receivers (excluding zero address)
    const receivers = transactions.filter(tx => tx.to.toLowerCase() !== ZERO_ADDRESS.toLowerCase());
    
    // Count occurrences of each recipient address
    const receiverCounts = {};
    receivers.forEach(tx => {
        const address = tx.to;
        receiverCounts[address] = (receiverCounts[address] || 0) + 1;
    });
    
    // Sort by count, descending
    const topReceivers = Object.entries(receiverCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    // Busiest days (if we have date information)
    const dateCounts = {};
    if (transactions[0] && transactions[0].date) {
        transactions.forEach(tx => {
            const date = tx.date;
            dateCounts[date] = (dateCounts[date] || 0) + 1;
        });
    }
    
    const busiestDays = Object.entries(dateCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    // Create summary text
    const summary = [
        "----- NFT TRANSACTION ANALYSIS -----",
        `Total Transactions: ${totalTransactions}`,
        `Total Mints: ${totalMints}`,
        `Total Transfers: ${totalTransfers}`,
        "",
        "----- TOP RECEIVERS -----",
        ...topReceivers.map(([address, count]) => `${address}: ${count} NFTs received`)
    ];
    
    // Add busiest days if available
    if (busiestDays.length > 0) {
        summary.push("");
        summary.push("----- BUSIEST DAYS -----");
        busiestDays.forEach(([date, count]) => summary.push(`${date}: ${count} transactions`));
    }
    
    // Log the summary
    summary.forEach(line => logger.info(line));
    
    // Save summary to file
    fs.writeFileSync(
        path.join(outputDirs.stats, 'analysis_summary.txt'),
        summary.join('\n')
    );
    
    // Save detailed stats as JSON
    const stats = {
        total_transactions: totalTransactions,
        total_mints: totalMints,
        total_transfers: totalTransfers,
        top_receivers: Object.fromEntries(topReceivers)
    };
    
    if (busiestDays.length > 0) {
        stats.busiest_days = Object.fromEntries(busiestDays);
    }
    
    fs.writeFileSync(
        path.join(outputDirs.stats, 'analysis_stats.json'),
        JSON.stringify(stats, null, 2)
    );
}

/**
 * Main function to execute the NFT analysis
 */
async function main() {
    // Parse command-line arguments
    const argv = yargs(hideBin(process.argv))
        .option('rpc', {
            description: 'Ethereum RPC URL (optional, overrides .env)',
            type: 'string'
        })
        .option('contract', {
            description: 'NFT contract address',
            demandOption: true,
            type: 'string'
        })
        .option('start', {
            description: 'Start block',
            default: 0,
            type: 'number'
        })
        .option('end', {
            description: 'End block',
            default: 'latest',
            type: 'string'
        })
        .option('batch', {
            description: 'Batch size for queries',
            default: 10000,
            type: 'number'
        })
        .option('output', {
            description: 'Base directory for output',
            default: 'output',
            type: 'string'
        })
        .help()
        .argv;
    
    // Setup directory structure
    const outputDirs = setupDirectories(argv.contract);
    
    // Setup logging
    const logger = setupLogging(outputDirs.logs);
    
    // Log run information
    logger.info(`Starting NFT Analysis for contract: ${argv.contract}`);
    logger.info(`Block range: ${argv.start} to ${argv.end}`);
    logger.info(`Output directories created at: ${outputDirs.main}`);
    
    // Save runtime parameters
    fs.writeFileSync(
        path.join(outputDirs.logs, 'run_parameters.json'),
        JSON.stringify(argv, null, 2)
    );
    
    try {
        // Connect to Ethereum - prioritize command-line argument over .env
        let provider;
        if (argv.rpc) {
            try {
                provider = new ethers.JsonRpcProvider(argv.rpc);
                await provider.getBlockNumber(); // Test connection
            } catch (e) {
                logger.warning(`Failed to connect using provided RPC. Trying fallback providers...`);
                provider = await getFallbackProvider(logger);
            }
        } else {
            provider = await getFallbackProvider(logger);
        }
        
        const currentBlock = await provider.getBlockNumber();
        logger.info(`Connected to Ethereum node. Current block: ${currentBlock}`);
        
        // Fetch logs
        const logs = await fetchTransferLogs(provider, argv.contract, {
            startBlock: argv.start,
            endBlock: argv.end,
            batchSize: argv.batch
        }, logger);
        
        if (!logs || logs.length === 0) {
            logger.error("No transfer logs found for this contract in the specified block range");
            process.exit(1);
        }
        
        logger.info(`Found ${logs.length} Transfer events`);
        
        // Decode logs
        const transactions = [];
        for (const log of logs) {
            const decoded = decodeTransferLog(log);
            
            // Add date if possible
            try {
                decoded.date = await getBlockTimestamp(provider, log.blockNumber);
            } catch (e) {
                decoded.date = "Unknown";
            }
            
            transactions.push(decoded);
        }
        
        // Save raw logs
        fs.writeFileSync(
            path.join(outputDirs.data, 'raw_logs.json'),
            JSON.stringify(logs.map(log => {
                // Create a safe copy with all BigInt values converted to strings
                const safeCopy = {};
                for (const [key, value] of Object.entries(log)) {
                    if (typeof value === 'bigint') {
                        safeCopy[key] = value.toString();
                    } else if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
                        // Handle nested objects
                        const nestedCopy = {};
                        for (const [nestedKey, nestedValue] of Object.entries(value)) {
                            if (typeof nestedValue === 'bigint') {
                                nestedCopy[nestedKey] = nestedValue.toString();
                            } else {
                                nestedCopy[nestedKey] = nestedValue;
                            }
                        }
                        safeCopy[key] = nestedCopy;
                    } else {
                        safeCopy[key] = value;
                    }
                }
                return safeCopy;
            }), null, 2)
        );
        
        // Save to CSV
        const csvPath = path.join(outputDirs.data, 'transactions.csv');
        const csvWriter = createCsvWriter({
            path: csvPath,
            header: [
                { id: 'txHash', title: 'TX_HASH' },
                { id: 'block', title: 'BLOCK' },
                { id: 'from', title: 'FROM' },
                { id: 'to', title: 'TO' },
                { id: 'tokenId', title: 'TOKEN_ID' },
                { id: 'type', title: 'TYPE' },
                { id: 'date', title: 'DATE' }
            ]
        });
        
        await csvWriter.writeRecords(transactions);
        logger.info(`Saved ${transactions.length} transactions to ${csvPath}`);
        
        // Save as JSON as well
        const jsonPath = path.join(outputDirs.data, 'transactions.json');
        fs.writeFileSync(jsonPath, JSON.stringify(transactions, null, 2));
        logger.info(`Saved JSON format to ${jsonPath}`);
        
        // Analyze the results
        analyzeTransfers(transactions, outputDirs, logger);
        
        // Create a README file in the output directory
        const readmeContent = `# NFT Analysis Results

## Overview
- **Contract Address**: ${argv.contract}
- **Block Range**: ${argv.start} to ${argv.end === 'latest' ? currentBlock : argv.end}
- **Analysis Date**: ${new Date().toISOString().split('T')[0]} ${new Date().toTimeString().split(' ')[0]}
- **Total Transactions**: ${transactions.length}

## Directory Structure
- **logs/**: Contains execution logs and run parameters
- **data/**: Contains raw and processed transaction data
- **stats/**: Contains analysis results and statistics

## Key Files
- **data/transactions.csv**: All decoded transactions in CSV format
- **data/transactions.json**: All decoded transactions in JSON format
- **data/raw_logs.json**: Raw blockchain logs
- **stats/analysis_summary.txt**: Summary of analysis findings
- **stats/analysis_stats.json**: Detailed statistics in JSON format
`;
        
        fs.writeFileSync(
            path.join(outputDirs.main, 'README.md'),
            readmeContent
        );
        
        // Create a symlink or copy the most recent output to a fixed location
        const latestLink = 'latest_output_js';
        if (fs.existsSync(latestLink)) {
            try {
                fs.unlinkSync(latestLink);
            } catch (e) {
                // If not a symlink, try removing as directory
                if (fs.statSync(latestLink).isDirectory()) {
                    fs.rmSync(latestLink, { recursive: true, force: true });
                }
            }
        }
        
        try {
            fs.symlinkSync(outputDirs.main, latestLink);
            logger.info(`Created symlink 'latest_output_js' -> ${outputDirs.main}`);
        } catch (e) {
            // If symlink not supported (e.g., on Windows), create a copy
            fs.cpSync(outputDirs.main, latestLink, { recursive: true });
            logger.info(`Created copy 'latest_output_js' from ${outputDirs.main}`);
        }
        
        logger.info(`Analysis complete. Results available in ${outputDirs.main}`);
        logger.info(`For quick access, use the 'latest_output_js' directory`);
    } catch (error) {
        logger.error(`Error during analysis: ${error.message}`, error);
        process.exit(1);
    }
}

// Run the main function
main().catch(error => {
    console.error("Unhandled error:", error);
    process.exit(1);
}); 