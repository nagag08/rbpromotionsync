import os
import requests
import json
import subprocess
import sys

def get_release_bundle_details(url, access_token, repository_key, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory, specifying the source repository.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}?project={project_key}&repository_key={repository_key}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print(f"::debug::Querying audit trail: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code == 404:
            print(f"::notice::Release bundle '{release_bundle}/{bundle_version}' not found at {url}. This may be expected.")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"::error::Failed to decode JSON response from {api_url}: {e}")
        return None

def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version, promotion_created_millis, project_key="default"):
    """
    Updates release bundle with correct timestamp for a specific promotion record.
    Returns parsed JSON data or None on failure.
    """
    try:
        promotion_created_millis = int(promotion_created_millis) + 1
    except (ValueError, TypeError):
        print(f"::warning::promotion_created_millis '{promotion_created_millis}' is not a valid number. Cannot increment.")
        pass

    api_url = f"{target_url}/lifecycle/api/v2/promotion/records/{release_bundle}/{bundle_version}?project={project_key}&operation=copy&promotion_created_millis={promotion_created_millis}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"Attempting to update/get promotion record with API: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None

def get_release_bundle_names_with_project_keys(source_url, access_token):
    """
    Gets list of release bundles with project key from /lifecycle/api/v2/release_bundle/names.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{source_url}/lifecycle/api/v2/release_bundle/names"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"Fetching release bundle names from: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None

def parse_repos_to_set(repo_list):
    """Converts a list of repositories into a set for order-independent comparison."""
    if not repo_list:
        return set()
    
    parsed_set = set()
    for item in repo_list:
        parsed_set.update(repo.strip() for repo in item.split(','))
    return parsed_set

def main():
    # --- Get all environment variables ---
    source_access_token = os.getenv("SOURCE_ACCESS_TOKEN")
    target_access_token = os.getenv("TARGET_ACCESS_TOKEN")
    source_url = os.getenv("SOURCE_URL")
    target_url = os.getenv("TARGET_URL")
    release_bundle_name = os.getenv("RELEASE_BUNDLE")
    bundle_version = os.getenv("BUNDLE_VERSION")
    environment = os.getenv("ENVIRONMENT")
    input_repository_key = os.getenv("REPOSITORY_KEY")
    jpd_origin = os.getenv("JPD_ORIGIN")
    # NEW: Get the fixed primary source URL
    primary_source_url = os.getenv("PRIMARY_SOURCE_URL")

    if not all([source_access_token, target_access_token, source_url, target_url, release_bundle_name, bundle_version, environment, input_repository_key, jpd_origin, primary_source_url]):
        print("::error::Missing one or more required environment variables. Ensure JPD_ORIGIN and PRIMARY_SOURCE_URL are set.")
        sys.exit(1)

    # --- Definitive Loop Prevention Check ---
    print(f"--- Checking event origin: Triggered from '{jpd_origin}' ---")
    
    # If the event came from any server that is NOT our designated primary source, stop.
    if jpd_origin != primary_source_url:
        print(f"\n✅ Event originated from '{jpd_origin}', which is not the primary source ('{primary_source_url}').")
        print("Ignoring event to prevent loop. Exiting successfully.")
        sys.exit(0)
    
    print(f"::notice::Event originated from the primary source server ('{primary_source_url}'). Proceeding with replication...")
    print("----------------------------------------------------------------")

    print(f"Processing bundle: {release_bundle_name}/{bundle_version}")
    print(f"Triggering and Target Environment: '{environment}'")

    print("\n--- Determining Project Key ---")
    project_key = "default" 
    names_response = get_release_bundle_names_with_project_keys(source_url, source_access_token)
    if names_response and "release_bundles" in names_response:
        for rb_info in names_response["release_bundles"]:
            if rb_info.get("repository_key") == input_repository_key:
                project_key = rb_info.get("project_key", "default")
                print(f"::notice::Matched repository_key '{input_repository_key}' to project_key '{project_key}'.")
                break
    else:
        print("::warning::Could not fetch release bundle names. Falling back to project_key 'default'.")

    print("\n--- Finding the exact triggering promotion event on the source server ---")
    source_audit_data = get_release_bundle_details(source_url, source_access_token, input_repository_key, release_bundle_name, bundle_version, project_key)
    
    source_promotion_event = None
    if source_audit_data and "audits" in source_audit_data:
        for event in source_audit_data.get("audits", []):
            if (event.get("subject_type") == "PROMOTION" and 
                not event.get("subject_reference", "").startswith("FED-")):
                
                event_environment = event.get("context", {}).get("environment")
                if str(event_environment) == str(environment):
                    print(f"::notice::Found matching source event for environment '{event_environment}'.")
                    source_promotion_event = event
                    break

    if not source_promotion_event:
        print(f"::error::Could not find a promotion event for '{environment}' in the source audit trail.")
        sys.exit(1)

    source_context = source_promotion_event.get("context", {})
    source_timestamp = source_context.get("promotion_created_millis")
    source_included_repos_set = parse_repos_to_set(source_context.get("included_repository_keys"))
    source_excluded_repos_set = parse_repos_to_set(source_context.get("excluded_repository_keys"))
    
    print("\n--- Checking latest promotion on target for an identical match ---")
    target_audit_data = get_release_bundle_details(target_url, target_access_token, input_repository_key, release_bundle_name, bundle_version, project_key)
    
    latest_target_promotion_event = None
    if target_audit_data and "audits" in target_audit_data:
        for audit_event in target_audit_data.get("audits", []):
            if (audit_event.get("subject_type") == "PROMOTION" and
                not audit_event.get("subject_reference", "").startswith("FED-")):
                latest_target_promotion_event = audit_event
                break

    if latest_target_promotion_event:
        target_context = latest_target_promotion_event.get("context", {})
        latest_target_environment = target_context.get("environment")
        
        if str(latest_target_environment) == str(environment):
            target_included_repos_set = parse_repos_to_set(target_context.get("included_repository_keys"))
            target_excluded_repos_set = parse_repos_to_set(target_context.get("excluded_repository_keys"))

            if (source_included_repos_set == target_included_repos_set and
                source_excluded_repos_set == target_excluded_repos_set):
                
                print("\n✅ Latest promotion on target is identical. Skipping.")
                sys.exit(0)
                
    print("::notice::Latest promotion on target is different or non-existent. Proceeding.")

    included_repository_keys = source_context.get("included_repository_keys", [])
    excluded_repository_keys = source_context.get("excluded_repository_keys", [])
    
    include_repos_param = f"--include-repos={','.join(included_repository_keys)}" if included_repository_keys else ""
    exclude_repos_param = f"--exclude-repos={','.join(excluded_repository_keys)}" if excluded_repository_keys else ""

    jf_rbp_command = ["jf", "rbp", release_bundle_name, bundle_version, environment, f"--project={project_key}"]
    if include_repos_param: jf_rbp_command.append(include_repos_param)
    if exclude_repos_param: jf_rbp_command.append(exclude_repos_param) 

    print("\n--- Executing JFrog CLI Command ---")
    print(f"Command: {' '.join(jf_rbp_command)}")
    try:
        result = subprocess.run(jf_rbp_command, check=True, capture_output=True, text=True)
        print("::notice::Release bundle promotion command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"::error::JFrog CLI command failed: {e.stderr}")
        sys.exit(e.returncode)

    updaterbresponse = update_release_bundle_milliseconds(target_url, target_access_token, release_bundle_name, bundle_version, source_timestamp, project_key)
    if updaterbresponse is None:
        print("::error::Failed to update release bundle promotion timestamp.")
        sys.exit(1)
    else:
        print("\n--- Update Release Bundle Timestamp Response ---")
        print(json.dumps(updaterbresponse, indent=2))

if __name__ == "__main__":
    main()
