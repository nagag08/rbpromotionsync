# JFrog hereby grants you a non-exclusive, non-transferable, non-distributable right 
# to use this  code   solely in connection with your use of a JFrog product or service. 
# This  code is provided 'as-is' and without any warranties or conditions, either 
# express or implied including, without limitation, any warranties or conditions of 
# title, non-infringement, merchantability or fitness for a particular cause. 
# Nothing herein shall convey to you any right or title in the code, other than 
# for the limited use right set forth herein. For the purposes hereof "you" shall
# mean you as an individual as well as the organization on behalf of which you
# are using the software and the JFrog product or service. 

# Script to sync existing Release bundles between source and target JPD

import os
import requests
import json
import subprocess
import sys
import argparse

def api_request(method, url, access_token, json_payload=None, params=None, timeout=30):
    """
    Generic function to make API requests and handle common errors.
    Returns parsed JSON data or None on failure.
    """
    print(f"DEBUG: Making {method} request to: {url}")
    if json_payload:
        print(f"DEBUG: Request payload: {json.dumps(json_payload)}")
    if params:
        print(f"DEBUG: Request params: {params}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_payload, params=params, timeout=timeout)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=json_payload, params=params, timeout=timeout)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params, timeout=timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status() 
        
        if response.status_code == 204 or not response.text:
            return {}
            
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print(f"ERROR: API request timed out to {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed to {url}: {e}")
        if e.response is not None:
            print(f"ERROR: Response status code: {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON response from {url}: {e}")
        if response is not None:
            print(f"ERROR: Response body: {response.text}")
        return None

def get_release_bundle_audit_history(jpd_url, access_token, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory and filters for COMPLETED PROMOTION events.
    Returns a sorted list of promotion event dictionaries or None on failure.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}"
    params = {"project": project_key}

    audit_data = api_request("GET", api_url, access_token, params=params)

    if audit_data is None:
        print(f"ERROR: Failed to retrieve audit data for {release_bundle}/{bundle_version} from {jpd_url}.")
        return None

    completed_promotions = []
    if "audits" in audit_data and isinstance(audit_data["audits"], list):
        for audit_event in audit_data["audits"]:
            if audit_event.get("subject_type") == "PROMOTION" and \
               audit_event.get("event_status") == "COMPLETED":
                completed_promotions.append(audit_event)
    
    completed_promotions.sort(key=lambda x: x.get('created_millis', 0))
    
    return completed_promotions

def get_release_bundle_names_with_project_keys(jpd_url, access_token):
    """
    Gets list of release bundles with project key from /lifecycle/api/v2/release_bundle/names.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/release_bundle/names"
    return api_request("GET", api_url, access_token)

def get_release_bundle_versions(jpd_url, access_token, release_bundle_name, project_key="default"):
    """
    Gets list of versions for a specific release bundle name.
    API: GET /lifecycle/api/v2/release_bundle/records/{release_bundle_name} 
    Returns a list of version dictionaries or None on failure.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/release_bundle/records/{release_bundle_name}" 
    params = {"project": project_key}

    response_data = api_request("GET", api_url, access_token, params=params)
    
    if response_data is None:
        print(f"ERROR: Failed to retrieve versions for bundle '{release_bundle_name}' from {jpd_url}.")
        return None
    
    print(str(response_data))
    
    # Corrected key to extract the list of versions based on your sample response
    return response_data.get("release_bundles", []) 

def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version, promotion_created_millis, project_key="default"):
    """
    Updates release bundle with correct timestamp for a specific promotion record.
    The function increments promotion_created_millis by 1.
    Returns parsed JSON data or None on failure.
    """
    try:
        updated_millis = int(promotion_created_millis) + 1
    except (ValueError, TypeError):
        print(f"WARNING: promotion_created_millis '{promotion_created_millis}' is not a valid number. Cannot increment. Using original value for API call.")
        updated_millis = promotion_created_millis
    
    # Note: This is often a PUT or POST request to update, not GET.
    # Verify the actual API for updating promotion records.
    api_url = f"{target_url}/lifecycle/api/v2/promotion/records/{release_bundle}/{bundle_version}?project={project_key}&operation=copy&promotion_created_millis={updated_millis}"
    
    return api_request("GET", api_url, access_token)


def main():
    parser = argparse.ArgumentParser(description="Synchronize Release Bundle promotions between two JFrog JPDs.")
    parser.add_argument("sourcetoken", nargs='?', help="Access Token for the Source JPD (API calls).")
    parser.add_argument("targettoken", nargs='?', help="Access Token for the Target JPD (API calls).")
    parser.add_argument("sourceurl", nargs='?', help="Base URL of the Source JPD (e.g., https://jpd1.jfrog.io).")
    parser.add_argument("targeturl", nargs='?', help="Base URL of the Target JPD (e.g., https://jpd2.jfrog.io).")
    parser.add_argument("environmentfilter", help="Optional: Only sync promotions to this specific environment (e.g., PROD).")

    args = parser.parse_args()

    # Assign parsed arguments to variables for clarity
    source_access_token = args.sourcetoken
    target_access_token = args.targettoken
    source_url = args.sourceurl
    target_url = args.targeturl
    environment_filter = args.environmentfilter

    print(f"INFO: Starting Release Bundle Synchronization process.")
    print(f"INFO: Source JPD: {source_url}")
    print(f"INFO: Target JPD: {target_url}")
    if environment_filter:
        print(f"INFO: Environment Filter: Only syncing promotions to '{environment_filter}'.")


    # --- Step 1: Discover all Release Bundle NAMES from the Source JPD ---
    print("\n--- Discovering Release Bundle NAMES from Source JPD ---")
    all_source_rb_names_info = get_release_bundle_names_with_project_keys(source_url, source_access_token)

    if not all_source_rb_names_info or not all_source_rb_names_info.get("release_bundles"):
        print("WARNING: No release bundle names found in the Source JPD or failed to retrieve list. Exiting.")
        sys.exit(0) # Exit gracefully if no bundles to process

    print(f"INFO: Found {len(all_source_rb_names_info['release_bundles'])} unique release bundle names in Source JPD.")

    total_versions_synced = 0 # Counter for unique name/version pairs that had promotions synced

    # --- Outer Loop: Iterate through each Release Bundle NAME ---
    for rb_name_info in all_source_rb_names_info["release_bundles"]:
        current_release_bundle_name = rb_name_info.get("release_bundle_name")
        # repository_key and project_key are associated with the bundle name
        current_input_repository_key = rb_name_info.get("repository_key") 
        current_project_key = rb_name_info.get("project_key", "default") 

        if not all([current_release_bundle_name, current_input_repository_key]):
            print(f"WARNING: Skipping malformed release bundle name entry: {rb_name_info}. Missing name or repository_key.")
            continue # Skip to the next bundle name if basic info is missing
        
        print(f"\n--- Processing Release Bundle Name: {current_release_bundle_name} (Project: {current_project_key}, Repo Key: {current_input_repository_key}) ---")

       # --- Step 2: Discover all VERSIONS for the current Release Bundle NAME ---
        print(f"INFO: Discovering VERSIONS for '{current_release_bundle_name}'...")
        # Pass the project key as a parameter as it's needed for the versions API as well
        all_source_rb_versions_info = get_release_bundle_versions(source_url, source_access_token, current_release_bundle_name, current_project_key)

        if not all_source_rb_versions_info:
            print(f"WARNING: No versions found for bundle '{current_release_bundle_name}' or failed to retrieve list. Skipping this bundle name.")
            continue # Skip to the next bundle name

        print(f"INFO: Found {len(all_source_rb_versions_info)} versions for '{current_release_bundle_name}'.")

        # --- Inner Loop: Iterate through each Release Bundle VERSION ---
        for rb_version_info in all_source_rb_versions_info:
            # Correctly get version from the response object
            current_bundle_version = rb_version_info.get("release_bundle_version") 
            if not current_bundle_version:
                print(f"WARNING: Skipping malformed version entry: {rb_version_info}. Missing release_bundle_version.")
                continue # Skip to the next version if info is missing

            print(f"\n--- Processing Release Bundle Version: {current_release_bundle_name}/{current_bundle_version} ---")
            
            # --- Get Promotion Histories from Source and Target JPDs ---
            print(f"INFO: Fetching Source JPD ({source_url}) Promotion History for {current_release_bundle_name}/{current_bundle_version}")
            source_promotions = get_release_bundle_audit_history(source_url, source_access_token, current_release_bundle_name, current_bundle_version, current_project_key)
            if source_promotions is None:
                print(f"ERROR: Skipping version {current_release_bundle_name}/{current_bundle_version} due to failure fetching source promotions.")
                continue # Skip to the next version for this name
            
            print(f"INFO: Source JPD has {len(source_promotions)} completed promotion events for this version.")

            print(f"INFO: Fetching Target JPD ({target_url}) Promotion History for {current_release_bundle_name}/{current_bundle_version}")
            target_promotions = get_release_bundle_audit_history(target_url, target_access_token, current_release_bundle_name, current_bundle_version, current_project_key)
            if target_promotions is None:
                print(f"ERROR: Skipping version {current_release_bundle_name}/{current_bundle_version} due to failure fetching target promotions.")
                continue # Skip to the next version for this name
            
            print(f"INFO: Target JPD has {len(target_promotions)} completed promotion events for this version.")

            # --- Identify Missing Promotions ---
            promotions_to_sync_for_version = []

            for source_promo in source_promotions:
                source_env = source_promo.get('context', {}).get('environment')
                source_inc_repos = tuple(source_promo.get('context', {}).get('included_repository_keys', []))
                source_exc_repos = tuple(source_promo.get('context', {}).get('excluded_repository_keys', []))

                if source_env is None:
                    print(f"WARNING: Source promotion event {source_promo.get('subject_reference')} missing environment data. Skipping.")
                    continue

                # Apply environment filter if specified
                if environment_filter and source_env != environment_filter:
                    print(f"INFO: Skipping promotion to '{source_env}' (not matching --environment-filter '{environment_filter}').")
                    continue

                is_present_in_target = False
                for target_promo in target_promotions:
                    target_env = target_promo.get('context', {}).get('environment')
                    target_inc_repos = tuple(target_promo.get('context', {}).get('included_repository_keys', []))
                    target_exc_repos = tuple(target_promo.get('context', {}).get('excluded_repository_keys', []))

                    # A promotion is considered present if the environment AND included/excluded repos match
                    if source_env == target_env and \
                       source_inc_repos == target_inc_repos and \
                       source_exc_repos == target_exc_repos:
                        is_present_in_target = True
                        break
                
                if not is_present_in_target:
                    promotions_to_sync_for_version.append(source_promo)
                    print(f"NOTICE: Promotion to '{source_env}' is missing in target and will be synced.")
                else:
                    print(f"INFO: Promotion to '{source_env}' is already present in target. Skipping.")

            if not promotions_to_sync_for_version:
                print(f"INFO: No missing promotions found for {current_release_bundle_name}/{current_bundle_version}.")
                continue # Move to the next version

            print(f"\n--- Found {len(promotions_to_sync_for_version)} Promotions to Synchronize for {current_release_bundle_name}/{current_bundle_version} ---")
            
            # --- Apply Missing Promotions to Target JPD ---
            for promo_event in promotions_to_sync_for_version:
                target_env_for_promo = promo_event.get('context', {}).get('environment')
                promo_inc_repos = promo_event.get('context', {}).get('included_repository_keys', [])
                promo_exc_repos = promo_event.get('context', {}).get('excluded_repository_keys', [])
                original_promotion_millis = promo_event.get('created_millis')

                if target_env_for_promo is None:
                    print(f"ERROR: Skipping promotion: Environment not found in event {promo_event.get('subject_reference')}.")
                    continue

                include_repos_param = ""
                if promo_inc_repos:
                    include_repos_str = ",".join(promo_inc_repos)
                    include_repos_param = f"--include-repos={include_repos_str}"

                exclude_repos_param = ""
                if promo_exc_repos:
                    exclude_repos_str = ",".join(promo_exc_repos)
                    exclude_repos_param = f"--exclude-repos={exclude_repos_str}"
                
                jf_rbp_command = [
                    "jf", "rbp",
                    current_release_bundle_name, # Use current name
                    current_bundle_version,    # Use current version
                    target_env_for_promo,      # Promote to this specific environment
                    f"--project={current_project_key}"
                ]

                if include_repos_param:
                    jf_rbp_command.append(include_repos_param)
                if exclude_repos_param:
                    jf_rbp_command.append(exclude_repos_param)

                print(f"\nNOTICE: Promoting {current_release_bundle_name}/{current_bundle_version} to {target_env_for_promo} in Target JPD...")
                print(f"  Command: {' '.join(jf_rbp_command)}")

                try:
                    result = subprocess.run(jf_rbp_command, check=True, capture_output=True, text=True)
                    print("STDOUT:\n", result.stdout)
                    print("STDERR:\n", result.stderr)
                    print(f"NOTICE: Successfully promoted {current_release_bundle_name}/{current_bundle_version} to {target_env_for_promo}.")
                except subprocess.CalledProcessError as e:
                    print(f"ERROR: Failed to promote {current_release_bundle_name}/{current_bundle_version} to {target_env_for_promo} (Exit Code: {e.returncode})")
                    print("STDOUT:\n", e.stdout)
                    print("STDERR:\n", e.stderr)
                    continue # Continue to next promotion for this bundle, or next bundle if no more promos
                
                # --- Optional: Update release bundle promotion timestamp in target ---
                if original_promotion_millis is not None and original_promotion_millis != "N/A":
                    print(f"NOTICE: Attempting to update timestamp in target JPD for promotion to {target_env_for_promo}...")
                    
                    updaterbresponse = update_release_bundle_milliseconds(
                        target_url, 
                        target_access_token, 
                        current_release_bundle_name, # Use current name
                        current_bundle_version,    # Use current version
                        original_promotion_millis, 
                        current_project_key        # Use current project key
                    )
                    
                    if updaterbresponse is None:
                        print(f"ERROR: Failed to update release bundle promotion timestamp for {target_env_for_promo}.")
                    else:
                        print(f"NOTICE: Timestamp update response for {target_env_for_promo}: {json.dumps(updaterbresponse, indent=2)}")
                else:
                    print(f"WARNING: Skipping timestamp update for {target_env_for_promo}: Original timestamp not available.")
            
            total_versions_synced += 1 # Increment only if at least one promotion was synced for this version

    print(f"\n--- Release Bundle Synchronization Complete. Total bundle versions processed/synced: {total_versions_synced} ---")


if __name__ == "__main__":
    main()

# Example 
# python3 sync_rb_promotions.py <source access token> <target access token>   <source jpd url> <target jpd url> ""
#  
# python3 sync_rb_promotions.py **** ***   http://172.18.104.154:8082 http://172.18.107.154:8082 ""
