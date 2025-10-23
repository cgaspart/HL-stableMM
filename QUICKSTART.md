# Quick Start Guide - Docker

Get your Hyperliquid Market Maker running in 3 minutes!

## Step 1: Create Environment File

```bash
cat > .env << EOF
WALLET_ADDRESS=your_wallet_address_here
PRIVATE_KEY=your_private_key_here
EOF
```

Replace `your_wallet_address_here` and `your_private_key_here` with your actual credentials.

## Step 2: Create Data Directory

```bash
mkdir -p data
```

## Step 3: Start the Container

```bash
docker-compose up -d
```

## Step 4: Access Dashboard

Open your browser: **http://localhost:5000**

## View Logs

```bash
docker-compose logs -f
```

## Stop

```bash
docker-compose down
```

---

That's it! Your market maker bot is now running with:
- ✅ Trading bot active
- ✅ API server running
- ✅ Dashboard accessible
- ✅ Database persisted in `./data/`
