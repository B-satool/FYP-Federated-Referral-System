# Put the system online for free (Oracle Cloud "Always Free")

Result: a link such as **`https://129-146-12-34.sslip.io`** that anyone can open in a browser, with no Docker or installation on their side.

- **Why Oracle:** its Always Free tier includes an ARM server with up to 4 CPUs and 24 GB RAM, free with no time limit. That's enough for all 11 containers. Other free tiers offer 1 GB, which is too small.
- **The address:** `sslip.io` turns the server's IP into a free hostname, and Caddy fetches a free HTTPS certificate for it automatically. No domain purchase is needed.

## Part 1: create the server (you, about 20 minutes)

1. **Sign up** at https://signup.cloud.oracle.com.
   - Choose your **home region** carefully, because it can't be changed. Pick one near you with good ARM capacity, e.g. *India West (Mumbai)*, *UAE East (Dubai)* or *Singapore*.
   - A debit or credit card is required **for verification only**. Always Free resources are never charged.
2. In the console, go to **☰ Menu → Compute → Instances → Create instance**.
   - **Name:** `fyp-referral`
   - **Image:** click *Change image* and choose **Canonical Ubuntu 24.04** (pick the ARM / aarch64 build if asked).
   - **Shape:** click *Change shape*, then **Ampere → VM.Standard.A1.Flex**. Set **4 OCPUs and 24 GB memory**. It's labelled *Always Free-eligible*.
   - **Networking:** keep the defaults (create a new virtual cloud network and public subnet). Make sure **Assign a public IPv4 address** is ticked.
   - **SSH keys:** select **Generate a key pair for me** and click **Download private key**. Keep the downloaded `.key` file; it's the server's password.
   - **Boot volume:** defaults are fine (50 GB, free).
   - Click **Create**. When the status turns **Running**, note the **Public IP address**.

   If you get **"Out of capacity"**, try another *Availability domain* in the same form, retry later, or temporarily choose 2 OCPU / 12 GB.
3. **Open the web ports in Oracle's firewall:**
   1. On the instance page, click the **Subnet** link, then **Security Lists → Default Security List → Add Ingress Rules**.
   2. Add rule 1: Source CIDR `0.0.0.0/0`, IP Protocol **TCP**, Destination port **80**.
   3. Add rule 2: the same, with destination port **443**.

   Port 22 (SSH) is already open by default.
4. Give your teammate or Claude the **public IP** and the **path to the downloaded `.key` file**.

## Part 2: install and start (one command on the server)

From any computer with the key (Windows PowerShell has `ssh` built in):

```powershell
ssh -i C:\path\to\ssh-key.key ubuntu@<PUBLIC-IP>
```

On the server:

```bash
git clone https://github.com/B-satool/FYP-Federated-Referral-System.git
cd FYP-Federated-Referral-System
bash scripts/deploy-server.sh
```

The script:
- installs Docker
- opens ports 80 and 443 in the server's own firewall (Oracle's Ubuntu images block them by default)
- creates `.env` with strong random secrets and `SITE_HOST=<ip-with-dashes>.sslip.io`
- builds and starts everything with `docker-compose.prod.yml`, which adds Caddy for HTTPS and hides every internal port
- loads the demo data
- prints the link

The first run takes 10–15 minutes.

If the GitHub repository is **private**, `git clone` asks for a username and a GitHub *personal access token* in place of the password.

## Using it

| What | Address |
|---|---|
| The app | `https://<SITE_HOST>` (demo accounts as in the README, password `demo1234`) |
| Keycloak admin console | `https://<SITE_HOST>/auth/admin`. User `admin`; the password is `KEYCLOAK_ADMIN_PASSWORD` in the server's `.env`. |

Common tasks (run on the server, in the project folder):

| Task | Command |
|---|---|
| Update to the latest code | `git pull && bash scripts/deploy-server.sh` |
| Reset demo data (before a demo) | `bash scripts/reset-and-seed.sh --force` |
| View logs | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f central` |
| Status | `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` |
| Add the AI key | Edit `.env` (`ANTHROPIC_API_KEY=...`), then `bash scripts/deploy-server.sh` |

## Security notes for a public link

- **Only the HTTPS front door is exposed.** The databases, APIs and Keycloak's admin port aren't reachable from the internet; Keycloak is reached through `/auth` behind the HTTPS front door.
- **The demo accounts use a known password (`demo1234`)**, and anyone with the link can sign in. That's acceptable only because all data is **synthetic**. For a longer-lived link, set `DEMO_USER_PASSWORD` to something private before the *first* deploy, because the password is applied when the accounts are first created.
- **Never put real patient data on this server.** It's a prototype; see the known limitations in `README.md`.

## Rehearsed locally

This exact setup was rehearsed on a laptop with `SITE_HOST=localhost` (Caddy then uses a self-signed certificate):
- HTTPS sign-in through `/auth` worked, and tokens carried the public issuer.
- Internal ports were hidden.
- The full browser journey (`web/e2e/smoke.spec.ts` journey 1, run with `WEB_URL=https://localhost IGNORE_HTTPS_ERRORS=1`) passed.
