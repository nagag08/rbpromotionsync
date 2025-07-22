# JFrog Release Bundle Promotion Sync

This repository contains a GitHub Actions workflow and a Python script designed to automate the replication of JFrog Artifactory Release Bundle promotions between two separate instances (a source and a target).

The solution is built to be robust, handling complex CI/CD scenarios like race conditions and recursive webhook triggers (loops). It uses secure OIDC authentication between GitHub Actions and the JFrog Platform.

---

## ✨ Features

* **Automated Replication**: Automatically replicates a promotion event from a source Artifactory to a target Artifactory.
* **Race Condition Handling**: Intelligently identifies the *exact* promotion event that triggered the workflow, even if other promotions for the same release bundle occur simultaneously.
* **Loop Prevention**: Includes a pre-flight check to determine if an identical promotion has already been replicated, preventing infinite webhook loops.
* **Secure OIDC Authentication**: Uses GitHub's OIDC provider to securely generate short-lived access tokens for both JFrog instances, eliminating the need for long-lived secrets.

---

## ⚙️ How It Works

The workflow is triggered by a webhook from a source Artifactory instance when a Release Bundle is promoted.

1.  **Trigger**: A user promotes a Release Bundle to a specific environment (e.g., `DEV`) on the **source** Artifactory.
2.  **Webhook**: A configured webhook in the source Artifactory fires, triggering the `workflow_dispatch` event in this repository's GitHub Actions workflow.
3.  **Authentication**: The GitHub Actions workflow uses its OIDC token to request temporary access tokens for both the source and target Artifactory instances.
4.  **Execute Script**: The workflow runs the `promote_release_bundle.py` script, passing information from the webhook payload (like bundle name, version, and environment) as environment variables.
5.  **Solve Race Condition**: The script takes the `environment` name from the trigger and queries the source Artifactory's audit API to find the exact promotion event that matches. This ensures it gets the correct repository list, even if a user has performed another promotion in the meantime.
6.  **Prevent Loop**: The script then performs a pre-flight check on the **target** Artifactory. It checks if the latest promotion for the bundle is already identical (same environment and repositories). If it is, the script exits successfully to prevent a loop.
7.  **Promote**: If the pre-flight check passes, the script uses the **JFrog CLI** to promote the Release Bundle on the target Artifactory.
8.  **Finalize**: The script makes a final API call to synchronize the promotion record's timestamp.

---

## 🚀 Setup and Configuration

Follow these steps to configure the replication workflow.

### 1. Repository Setup

1.  Place the `promote_release_bundle.py` script in the root of your repository.
2.  Place the `release_bundle_source.yml` workflow file in the `.github/workflows/` directory.

### 2. JFrog Webhook Configuration

You need to configure a webhook on your **source** Artifactory instance.

* **Go to**: `Administration` -> `General` -> `Webhooks`
* **Event Type**: Select `Release Bundle Promotion Completed`.
* **URL**: Provide the GitHub Actions `workflow_dispatch` URL:
    ```
    [https://api.github.com/repos/nareshp1234/rbpromotionsync/actions/workflows/rbpromotion.yml/dispatches](https://api.github.com/repos/nareshp1234/rbpromotionsync/actions/workflows/rbpromotion.yml/dispatches)
    ```
* **Payload**: Use the following JSON payload to send the required data to the workflow. This maps the event data to the `inputs` defined in your `.yml` file.
    ```json
    {
      "event": "workflow_dispatch",
      "client_payload": {
        "name": "Event triggered by {{.domain}}.{{.event_type}} from {{.jpd_origin}}",
        "release_bundle": "{{.data.release_bundle_name}}",
        "bundle_version": "{{.data.release_bundle_version}}",
        "environment": "{{.data.environment}}",
        "repository_key": "{{.data.repository_key}}",
        "sourceurl": "YOUR_SOURCE_URL_HERE",
        "targeturl": "YOUR_TARGET_URL_HERE"
      }
    }
    ```
    > **Note**: Replace `YOUR_SOURCE_URL_HERE` and `YOUR_TARGET_URL_HERE` with your actual Artifactory hostnames (e.g., `psemea.jfrog.io`).

### 3. GitHub Actions Configuration

Your workflow file (`release_bundle_source.yml`) is already configured to read inputs and set up the environment. The primary dependency is configuring OIDC between GitHub and your JFrog instances.

* **JFrog OIDC Integration**: Ensure you have set up an OIDC integration in both of your JFrog instances that trusts your GitHub repository. The `oidc-provider-name` (`nareshgithub` in your workflow) must match the name of the provider configured in JFrog.

---

## 📋 Environment Variables

The Python script consumes the following environment variables, which are set by the GitHub Actions workflow:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `SOURCE_ACCESS_TOKEN` | A temporary OIDC token for the source Artifactory. | `***` |
| `TARGET_ACCESS_TOKEN` | A temporary OIDC token for the target Artifactory. | `***` |
| `SOURCE_URL` | The full URL of the source Artifactory. | `https://psemea.jfrog.io` |
| `TARGET_URL` | The full URL of the target Artifactory. | `https://psazuse.jfrog.io` |
| `RELEASE_BUNDLE` | The name of the release bundle being promoted. | `npmexample` |
| `BUNDLE_VERSION` | The version of the release bundle. | `6.0` |
| `ENVIRONMENT` | The name of the environment from the trigger. Used for both source correlation and as the target environment name. | `QA` |
| `REPOSITORY_KEY` | The repository where the release bundle is stored. | `nd-release-bundles-v2` |
