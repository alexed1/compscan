# Competitor Website Monitoring Tool

An automated tool that monitors competitor websites for changes, analyzes them using AI, and sends intelligent email digests.

## Features

- **Automated Daily Monitoring**: Runs daily via GitHub Actions cron schedule
- **Smart Web Scraping**: Uses httpx for static pages with automatic Playwright fallback for JavaScript-rendered content
- **Change Detection**: Hash-based content diffing to detect when pages change
- **AI-Powered Analysis**: Uses Claude Sonnet 4 to analyze changes and provide competitive intelligence insights
- **Email Alerts**: Sends professional HTML email digests via Resend
- **Version Control**: Automatically commits snapshots back to the repository
- **Configurable**: Easy YAML configuration for competitor URLs

## Architecture

```
compscan/
├── .github/
│   └── workflows/
│       └── monitor.yml          # GitHub Actions workflow
├── src/
│   └── monitor.py               # Main monitoring script
├── snapshots/                   # Stored page snapshots (auto-generated)
├── config.yaml                  # Configuration file
├── requirements.txt             # Python dependencies
└── README.md
```

## Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd compscan
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Competitor URLs

Edit `config.yaml` to add your competitor URLs:

```yaml
competitors:
  - name: "Competitor A - Homepage"
    url: "https://www.competitor-a.com"
    requires_js: false

  - name: "Competitor B - Pricing"
    url: "https://www.competitor-b.com/pricing"
    requires_js: true  # Set to true for JS-heavy pages
```

### 4. Set Up API Keys

You need two API keys:

1. **Anthropic API Key**: Get it from [console.anthropic.com](https://console.anthropic.com)
2. **Resend API Key**: Get it from [resend.com](https://resend.com)

#### For Local Testing

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export RESEND_API_KEY="your-resend-api-key"
```

#### For GitHub Actions

Add these as repository secrets:

1. Go to your GitHub repository
2. Navigate to Settings > Secrets and variables > Actions
3. Add the following secrets:
   - `ANTHROPIC_API_KEY`
   - `RESEND_API_KEY`

### 5. Configure Email Settings

Update the email section in `config.yaml`:

```yaml
email:
  from_email: "monitoring@yourdomain.com"
  from_name: "Competitor Intelligence Monitor"
  to_emails:
    - "team@yourdomain.com"
  subject_prefix: "[Competitor Alert]"
```

**Note**: You must verify your sending domain in Resend before emails will be delivered.

## Usage

### Manual Run (Local)

```bash
python src/monitor.py
```

### Automated Runs (GitHub Actions)

The tool automatically runs daily at 9 AM UTC via GitHub Actions. You can also:

- **Manual Trigger**: Go to Actions tab > Competitor Monitoring > Run workflow
- **Push to Main**: Workflow runs automatically when you push changes to `src/`, `config.yaml`, or the workflow file

### Monitoring Schedule

By default, monitoring runs daily at 9 AM UTC. To change the schedule, edit `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    - cron: '0 9 * * *'  # Change this line
```

Use [crontab.guru](https://crontab.guru) to help with cron syntax.

## How It Works

1. **Scraping**: For each competitor URL, the tool attempts to scrape content using httpx (fast). If that fails or if `requires_js: true`, it falls back to Playwright (slower but handles JavaScript).

2. **Change Detection**: Content is hashed using SHA-256. If the hash differs from the previous snapshot, a change is detected.

3. **Snapshot Storage**: Current content is saved to `snapshots/` directory as JSON files. These are committed back to the repository.

4. **AI Analysis**: All detected changes are sent to Claude Sonnet 4 with a competitive intelligence analyst prompt to generate insights.

5. **Email Digest**: An HTML email is sent with:
   - List of changed competitor pages
   - AI-generated analysis and recommendations
   - Links to the changed pages

## Configuration Reference

### Monitoring Settings

```yaml
monitoring:
  check_interval: 24        # Hours between checks (informational)
  user_agent: "Mozilla..."  # User agent for scraping
  timeout: 30               # Request timeout in seconds
```

### Anthropic API Settings

```yaml
anthropic:
  model: "claude-sonnet-4"  # AI model to use
  max_tokens: 4096          # Max tokens for analysis
```

### Competitor Configuration

```yaml
competitors:
  - name: "Unique name"     # Descriptive name
    url: "https://..."      # Full URL to monitor
    requires_js: false      # true = use Playwright, false = try httpx first
```

## Snapshot Format

Snapshots are stored as JSON in the `snapshots/` directory:

```json
{
  "name": "Competitor A - Homepage",
  "url": "https://www.competitor-a.com",
  "timestamp": "2024-01-15T09:00:00.000000",
  "content_hash": "sha256-hash",
  "content": "First 10,000 characters..."
}
```

## Troubleshooting

### Scraping Failures

- Check if the URL is accessible
- For JavaScript-heavy sites, set `requires_js: true`
- Increase `timeout` in config.yaml
- Check GitHub Actions logs for detailed error messages

### Email Not Sending

- Verify your domain in Resend
- Check that `RESEND_API_KEY` is set correctly
- Ensure `from_email` uses your verified domain
- Check Resend dashboard for delivery logs

### No Changes Detected

- First run always detects changes (creates initial snapshots)
- Changes detected by SHA-256 hash comparison
- Even minor HTML changes will trigger detection
- Check snapshots/ directory to see stored content

### GitHub Actions Failures

- Verify secrets are set correctly
- Check workflow logs in Actions tab
- Ensure repository has write permissions
- Test locally first with `python src/monitor.py`

## Cost Considerations

- **Anthropic API**: Charges per token. ~$3-5 per month for daily monitoring of 8 URLs.
- **Resend**: Free tier includes 100 emails/day, 3,000/month.
- **GitHub Actions**: 2,000 minutes/month free for public repos.

## Security Notes

- Never commit API keys to the repository
- Use GitHub Secrets for sensitive credentials
- Review scraping compliance with target sites' terms of service
- Be respectful with scraping frequency (daily is reasonable)

## License

MIT

## Contributing

Issues and pull requests welcome!
