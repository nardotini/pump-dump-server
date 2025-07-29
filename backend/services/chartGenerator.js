class ChartGenerator {
    constructor() {
        this.priceHistory = [];
        this.currentPrice = 100;
        this.volatility = 0.02;
        this.trend = 0;
    }

    generateNextPoint(forceDirection = null) {
        // Add some trending behavior
        if (forceDirection === 'pump') {
            this.trend = 0.001;
        } else if (forceDirection === 'dump') {
            this.trend = -0.001;
        }

        // Random walk with trend
        const random = (Math.random() - 0.5) * 2;
        const change = (random * this.volatility) + this.trend;
        
        this.currentPrice *= (1 + change);
        
        // Add some excitement with occasional big moves
        if (Math.random() < 0.05) {
            this.currentPrice *= Math.random() > 0.5 ? 1.05 : 0.95;
        }

        this.priceHistory.push({
            time: Date.now(),
            price: this.currentPrice
        });

        // Keep last 100 points
        if (this.priceHistory.length > 100) {
            this.priceHistory.shift();
        }

        return this.currentPrice;
    }

    generateGameSequence(duration, result) {
        const sequence = [];
        const steps = duration * 2; // 2 updates per second
        
        // Start neutral
        for (let i = 0; i < steps * 0.7; i++) {
            sequence.push(this.generateNextPoint());
        }

        // Build tension - make it look like opposite might win
        const fakeDirection = result === 'pump' ? 'dump' : 'pump';
        for (let i = 0; i < steps * 0.2; i++) {
            sequence.push(this.generateNextPoint(fakeDirection));
        }

        // DRAMATIC REVERSAL for the win!
        for (let i = 0; i < steps * 0.1; i++) {
            this.volatility = 0.1; // Increase volatility for drama
            sequence.push(this.generateNextPoint(result));
        }

        return sequence;
    }

    reset() {
        this.priceHistory = [];
        this.currentPrice = 100;
        this.trend = 0;
        this.volatility = 0.02;
    }
}

module.exports = ChartGenerator;