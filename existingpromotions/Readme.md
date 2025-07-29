# JFrog Release Bundle Promotion History Sync

This repository contains a Python script designed to perform a bulk synchronization of existing JFrog Artifactory Release Bundle promotion histories from a source JFrog Platform Deployment (JPD) to a target JPD.

This tool is ideal for migration, disaster recovery, or backfilling promotion records to ensure two JFrog instances are in sync. It is robust enough to handle complex promotion histories, including re-promotions to the same environment.

---

## ✨ Features

* **Comprehensive Sync**: Discovers all Release Bundles and all their versions on the source JPD.
* **Idempotent & Accurate**: Intelligently counts the occurrences of each unique promotion on both the source and target. It only syncs the difference, making it safe to run multiple times.
* **Handles Re-Promotions**: Correctly synchronizes complex lifecycles where a bundle is promoted to the same environment multiple times (e.g., `DEV` -> `QA` -> `PROD` -> `QA`).
* **Detailed Comparison**: A promotion is considered unique based on its environment and the exact set of included/excluded repositories.
* **Flexible Filtering**: Optionally allows you to sync promotions for only one specific project or environment.
* **Command-Line Driven**: Easy to run manually or from any CI/CD platform.

---

## 🔧 How It Works

The script performs a comprehensive, multi-level scan to ensure accuracy:

1.  **Configure CLI**: It first configures the JFrog CLI to point to the target JPD, ensuring all promotion commands are sent to the correct destination.
2.  **Discover Names**: It queries the source JPD to get a list of all Release Bundle names.
3.  **Discover Versions**: For each name, it fetches all available versions.
4.  **Compare Histories**: For each `name/version` pair, it gets the complete promotion history from both the source and the target JPDs.
5.  **Count Promotions**: Instead of just checking for existence, it **counts** how many times each unique promotion (environment + repos) appears on both servers.
6.  **Identify Missing Promotions**: It builds a list of promotions where the count on the source is greater than the count on the target.
7.  **Replicate Promotions**: It iterates through the "missing" list and uses the **JFrog CLI** (`jf rbp`) to execute the promotion on the target JPD, replicating the original state.

---

## 🚀 Setup and Usage

### Prerequisites

* Python 3 with the `requests` library installed (`pip install requests`).
* **JFrog CLI** installed on the machine running the script and available in the system's `PATH`.
* Network connectivity from the script's location to both the source and target JPDs.
* Valid access tokens for both JPDs with sufficient permissions (at a minimum: Read on source, Promote Release Bundle on target).
* **Important**: This script only syncs the promotion *metadata*. The underlying artifacts referenced by the Release Bundles **must** already exist on the target JPD for the `jf rbp` command to succeed.

### Execution

The script is run from the command line.

#### **Syntax**

```bash
python3 sync_rb_promotions.py <SOURCE_TOKEN> <TARGET_TOKEN> <SOURCE_URL> <TARGET_URL> [ENVIRONMENT_FILTER] [--project-filter <PROJECT_KEY>]

Arguments
Argument

Description

Required

Example

SOURCE_TOKEN

An access token for the source JPD.

Yes

eyJ...

TARGET_TOKEN

An access token for the target JPD.

Yes

eyJ...

SOURCE_URL

The full base URL of the source JPD.

Yes

https://my-source.jfrog.io

TARGET_URL

The full base URL of the target JPD.

Yes

https://my-target.jfrog.io

ENVIRONMENT_FILTER

Optional: The specific environment to sync (e.g., "PROD"). To sync all, provide empty quotes "".

No

"PROD"

--project-filter

Optional: The specific project key to sync. If omitted, all projects are considered.

No

my-project-key

Examples
Sync all promotions for all projects:

python3 sync_rb_promotions.py <source_token> <target_token> [https://source.jfrog.io](https://source.jfrog.io) [https://target.jfrog.io](https://target.jfrog.io) ""

Sync only promotions for the nd project:

python3 sync_rb_promotions.py <source_token> <target_token> [https://source.jfrog.io](https://source.jfrog.io) [https://target.jfrog.io](https://target.jfrog.io) "" --project-filter "nd"

Sync only PROD promotions for the nd project:

python3 sync_rb_promotions.py <source_token> <target_token> [https://source.jfrog.io](https://source.jfrog.io) [https://target.jfrog.io](https://target.jfrog.io) "PROD" --project-filter "nd"
