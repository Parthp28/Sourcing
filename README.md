# Job Pulse Sourcing

Job Pulse monitors public company career boards every hour and sends newly
discovered US software, data, and AI/ML engineering opportunities to a Google
Sheet. It is designed to run in a public GitHub repository without storing any
applicant profile, resume, contact details, or application history in Git.

## Current coverage

The collector supports:

- Greenhouse
- Lever
- Ashby
- Workday
- Amazon Jobs
- SmartRecruiters
- Workable
- Recruitee

The registry in `config/companies.yaml` determines which employers are scanned.
Adding fetcher code alone does not add coverage; an employer must also be present
in the registry with a valid ATS token.

## Pipeline

```text
companies.yaml
  -> concurrent public ATS requests
  -> normalize jobs
  -> reject explicit non-US and clearly ineligible roles
  -> retain uncertain roles as Review
  -> deduplicate using company + ATS job ID
  -> append new candidates to Google Sheets
```

The system does not assume that an unknown location is in the United States.
Explicit US locations are marked `Apply`, ambiguous locations such as plain
`Remote` are marked `Review`, and explicit foreign locations are discarded.

## Privacy boundary

This public repository must never contain:

- Personal contact information
- Resume source files or generated resumes
- Work authorization documents
- Application answers or history
- Google service-account JSON
- API keys or database credentials

Credentials belong only in GitHub Actions Secrets. Resume tailoring and form
autofill belong in a separate private repository.

## Google Sheet setup

1. Create a Google Sheet and copy its ID from the URL.
2. Enable the Google Sheets API in a Google Cloud project.
3. Create a service account and download its JSON key.
4. Share the Sheet with the service-account email as Editor.
5. Add these GitHub Actions secrets:
   - `GOOGLE_SERVICE_ACCOUNT_JSON`
   - `SHEET_ID`
6. Trigger the `scan` workflow manually once, then let the hourly cron run.

The workflow runs at minute 17 of every hour to reduce scheduling congestion.
GitHub scheduled workflows can still start late, so `Discovered` is the actual
first-seen timestamp rather than an assertion about the employer's publish time.

## Adding a company

Add one record to `config/companies.yaml`:

```yaml
- {name: Stripe, ats: greenhouse, token: stripe}
```

The token normally comes from the employer's hosted career-board URL. Run the
verification script after a larger registry change:

```bash
python scripts/verify_companies.py
```

## Local verification

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

To perform a live local scan, also export `GOOGLE_SERVICE_ACCOUNT_JSON` and
`SHEET_ID`, then run `python main.py`.

## Next coverage work

The initial uploaded registry contains 224 companies and is heavily weighted
toward Greenhouse. The next milestone is to expand and verify the registry,
especially for Lever, Workday, SmartRecruiters, iCIMS, and Eightfold employers.
