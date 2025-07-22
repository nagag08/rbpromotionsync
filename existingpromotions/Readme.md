````markdown
# JFrog Release Bundle Promotion History Sync

This repository contains a Python script designed to perform a bulk synchronization of existing JFrog Artifactory Release Bundle promotion histories from a source JFrog Platform Deployment (JPD) to a target JPD.

This tool is ideal for migration, disaster recovery, or backfilling promotion records to ensure two JFrog instances are in sync.

---

## ✨ Features

* **Comprehensive Sync**: Discovers all Release Bundles and all their versions on the source JPD.
* **Idempotent**: Intelligently compares the promotion history of each Release Bundle version against the target and only creates promotions that are missing. It is safe to run multiple times.
* **Detailed Comparison**: A promotion is only considered "missing" if the target does not have a promotion for the same environment with the exact same included and excluded repositories.
* **Environment Filtering**: Optionally allows you to sync promotions for only one specific environment (e.g., only sync `PROD` promotions).
* **Command-Line Driven**: Easy to run manually or from any CI/CD platform.

---

## 🔧 How It Works

The script performs a comprehensive, multi-level scan to ensure accuracy:

1.  **Discover Names**: It first queries the source JPD to get a list of all Release Bundle names.
2.  **Discover Versions**: For each name, it fetches all available versions.
3.  **Compare Histories**: For each `name/version` pair, it gets the complete promotion history from both the source and the target JPDs.
4.  **Identify Missing Promotions**: It compares the two histories and builds a list of promotion events that exist on the source but are missing on the target.
5.  **Replicate Promotions**: It iterates through the "missing" list and uses the **JFrog CLI** (`jf rbp`) to execute the promotion on the target JPD, replicating the original state.
6.  **Update Timestamps**: After each successful promotion, it makes an API call to update the timestamp to align with the original promotion time from the source.

---

## 🚀 Setup and Usage

### Prerequisites

* Python 3 with the `requests` library installed (`pip install requests`).
* **JFrog CLI** installed on the machine running the script and available in the system's `PATH`.
* Network connectivity from the script's location to both the source and target JPDs.
* Valid access tokens for both JPDs with sufficient permissions (at a minimum: Read on source, Promote Release Bundle on target).
* **Important**: This script only syncs the promotion *metadata*. The underlying artifacts referenced by the Release Bundles **must** already exist on the target JPD for the `jf rbp` command to succeed.

### Execution

The script is run from the command line with five arguments.

#### **Syntax**

```bash
python3 sync_rb_promotions.py <SOURCE_TOKEN> <TARGET_TOKEN> <SOURCE_URL> <TARGET_URL> <ENVIRONMENT_FILTER>
````

#### **Arguments**

| Argument           | Description                                                                                          | Required | Example                    |
| :----------------- | :--------------------------------------------------------------------------------------------------- | :------- | :------------------------- |
| `SOURCE_TOKEN`     | An access token for the source JPD.                                                                  | Yes      | `eyJ...`                   |
| `TARGET_TOKEN`     | An access token for the target JPD.                                                                  | Yes      | `eyJ...`                   |
| `SOURCE_URL`       | The full base URL of the source JPD.                                                                 | Yes      | `https://my-source.jfrog.io` |
| `TARGET_URL`       | The full base URL of the target JPD.                                                                 | Yes      | `https://my-target.jfrog.io` |
| `ENVIRONMENT_FILTER` | The specific environment to sync (e.g., "PROD"). To sync all environments, provide empty quotes `""`. | Yes      | `"PROD"` or `""`             |

#### **Examples**

  * **To sync all promotions for all environments:**
    ```bash
    python3 sync_rb_promotions.py <source_token> <target_token> [https://source.jfrog.io](https://source.jfrog.io) [https://target.jfrog.io](https://target.jfrog.io) ""
    ```
  * **To sync ONLY promotions to the `PROD` environment:**
    ```bash
    python3 sync_rb_promotions.py <source_token> <target_token> [https://source.jfrog.io](https://source.jfrog.io) [https://target.jfrog.io](https://target.jfrog.io) "PROD"
    ```

-----

## 📜 License / Disclaimer

```
JFrog hereby grants you a non-exclusive, non-transferable, non-distributable right 
to use this  code   solely in connection with your use of a JFrog product or service. 
This  code is provided 'as-is' and without any warranties or conditions, either 
express or implied including, without limitation, any warranties or conditions of 
title, non-infringement, merchantability or fitness for a particular cause. 
Nothing herein shall convey to you any right or title in the code, other than 
for the limited use right set forth herein. For the purposes hereof "you" shall
mean you as an individual as well as the organization on behalf of which you
are using the software and the JFrog product or service. 
```

```
```
