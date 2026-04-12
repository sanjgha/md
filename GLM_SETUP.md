# GLM-5.1 Trading Agent Setup

## Quick Setup Steps

### 1. Get Your GLM API Key

1. Visit https://open.bigmodel.cn/
2. Register/login to your account
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the API key (format: `id.secret`)

### 2. Check API Quota & Pricing

Before using the API, check your account:
1. Visit https://open.bigmodel.cn/console
2. Check "Balance" or "Usage" section
3. GLM-4: ~¥0.50 per 1M tokens (often has free tier)
4. GLM-5.1: ~¥1.00 per 1M tokens (requires paid plan)

**Note**: New accounts often get free credits for GLM-4!

### 3. Add API Key to .env File

```bash
# Navigate to project directory
cd /home/ubuntu/projects/md

# Edit .env file
nano .env

# Add this line (replace with your actual key):
GLM_API_KEY=your-actual-glm-api-key-here

# Save and exit (Ctrl+X, then Y, then Enter)
```

### 3. Test the Analysis

```bash
# Test with today's scanner results
python3 -m src.main analyze --days 1

# Or test with specific scanner
python3 -m src.main analyze --scanner momentum --days 1

# Or override API key temporarily
python3 -m src.main analyze --api-key "your-key-here" --days 1
```

## Current .env Structure

Your `.env` file should look like this:

```bash
# Database
DATABASE_URL=postgresql://market_data:market_data@localhost:5432/market_data

# MarketData.app API
MARKETDATA_API_TOKEN=V3JkeVpHVEgtODFtVjBDRVYwN1oyeW91amdva1FtN2hfaEExTUdjNFA4TT0

# GLM API (Zhipu AI - GLM-5.1 for trading analysis)
GLM_API_KEY=your-glm-api-key-here

# Application
LOG_LEVEL=INFO
LOG_FILE=logs/market_data.log
```

## Usage Examples

### Basic Analysis
```bash
python3 -m src.main analyze
```

### Analyze Specific Scanner
```bash
python3 -m src.main analyze --scanner price_action
```

### Analyze Multiple Days
```bash
python3 -m src.main analyze --days 3
```

### Scheduled Analysis (via systemd)
The analysis service runs automatically at 9:00 AM ET:
```bash
systemctl status market-data-analyze.service
```

## GLM-5.1 Model Features

- **Model**: `glm-5.1` (latest from Zhipu AI)
- **Max Tokens**: 4000
- **Temperature**: 0.7 (balanced creativity)
- **Timeout**: 60 seconds

## Troubleshooting

### API Key Not Working
```bash
# Test API key manually
curl -X POST https://open.bigmodel.cn/api/paas/v4/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"model":"glm-5.1","messages":[{"role":"user","content":"Hello"}]}'
```

### Environment Variable Not Loading
```bash
# Reload .env file
source /home/ubuntu/projects/md/.env

# Or check if variable is set
echo $GLM_API_KEY
```

### Analysis Timeout
- GLM-5.1 may take longer for complex analyses
- Timeout is set to 60 seconds
- If timing out, reduce `--days` parameter

## Cost Considerations

GLM-5.1 API costs:
- Free tier: Limited requests per day
- Paid tier: ~¥0.50 per 1M tokens (input)
- Typical analysis: ~2000 tokens = ~¥0.001 per analysis

## Alternative Models

If GLM-5.1 is unavailable, the system can be easily adapted to:
- GLM-4 (faster, cheaper)
- Other Chinese LLMs via API
- Local models (requires additional setup)

## Next Steps

1. ✅ Get API key from https://open.bigmodel.cn/
2. ✅ Add to `.env` file
3. ✅ Test with `python3 -m src.main analyze --days 1`
4. ✅ Check scheduled service status
