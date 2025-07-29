// backend/services/escrow.js
const { Connection, PublicKey, Keypair, SystemProgram, Transaction } = require('@solana/web3.js');
const { Program, AnchorProvider } = require('@project-serum/anchor');

class SolanaEscrow {
    constructor() {
        this.connection = new Connection(process.env.SOLANA_RPC);
        this.escrowWallet = Keypair.fromSecretKey(/* your escrow wallet */);
    }

    async generatePaymentAddress(userId, roundId, amount, betType) {
        // Generate unique address for this bet
        // This lets us track who paid what
        const seed = `${userId}_${roundId}_${betType}_${Date.now()}`;
        const [paymentPDA] = await PublicKey.findProgramAddress(
            [Buffer.from(seed)],
            this.escrowProgram.programId
        );
        
        // Store in database
        await db.createPendingBet({
            userId,
            roundId,
            amount,
            betType,
            paymentAddress: paymentPDA.toString(),
            status: 'pending'
        });

        return paymentPDA.toString();
    }

    async checkPayment(paymentAddress) {
        const balance = await this.connection.getBalance(new PublicKey(paymentAddress));
        return balance > 0;
    }

    async distributePayout(roundId, winners, totalPot) {
        const HOUSE_FEE = 0.05; // 5% (you can make it 10%!)
        const houseCut = totalPot * HOUSE_FEE;
        const winnerPot = totalPot - houseCut;

        // Send house cut to your wallet
        await this.sendSol(this.houseWallet, houseCut);

        // Distribute to winners proportionally
        for (const winner of winners) {
            const winnerShare = (winner.betAmount / winner.totalBetAmount) * winnerPot;
            await this.sendSol(winner.wallet, winnerShare);
        }
    }
}