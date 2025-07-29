class AntiCheat {
    constructor(redis) {
        this.redis = redis;
        this.suspiciousPatterns = new Map();
    }

    async checkBet(userId, betData) {
        const checks = await Promise.all([
            this.checkRapidBetting(userId),
            this.checkPatternAbuse(userId, betData),
            this.checkMultiAccount(betData.ip, betData.deviceId),
            this.checkVPNUsage(betData.ip)
        ]);

        const flags = checks.filter(c => c.flagged);
        
        if (flags.length > 0) {
            await this.logSuspiciousActivity(userId, flags);
            
            // Soft ban for suspicious activity
            if (flags.length >= 2) {
                await this.shadowBan(userId, '1h');
                return { allowed: false, reason: 'Suspicious activity detected' };
            }
        }

        return { allowed: true };
    }

    async checkRapidBetting(userId) {
        const key = `rapid_bet:${userId}`;
        const count = await this.redis.incr(key);
        
        if (count === 1) {
            await this.redis.expire(key, 10); // 10 second window
        }

        return {
            flagged: count > 5, // More than 5 bets in 10 seconds
            reason: 'Rapid betting detected'
        };
    }

    async checkMultiAccount(ip, deviceId) {
        const key = `device:${deviceId}:users`;
        await this.redis.sadd(key, userId);
        await this.redis.expire(key, 3600);

        const userCount = await this.redis.scard(key);

        return {
            flagged: userCount > 3, // More than 3 accounts per device
            reason: 'Multiple accounts detected'
        };
    }
}