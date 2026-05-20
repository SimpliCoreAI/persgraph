# Streamlit UI

Run on Windows, access from Mac browser via Tailscale.

## Setup

```powershell
pip install streamlit plotly
```

## Run

```powershell
# From the repo root on Windows
streamlit run streamlit/app.py --server.address 100.122.130.89 --server.port 8501
```

## Access from Mac

```
http://100.122.130.89:8501
```

## Firewall rule (run once on Windows as Admin)

```powershell
New-NetFirewallRule -DisplayName "Allow Streamlit Tailscale" `
  -Direction Inbound -Protocol TCP -LocalPort 8501 `
  -RemoteAddress "100.0.0.0/8" -Action Allow
```
