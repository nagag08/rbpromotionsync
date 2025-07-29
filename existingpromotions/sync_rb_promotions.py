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
from collections import Counter

def api_request(method, url, access_token, json_payload=None, params=None, timeout=30):
    """
    Generic function to make API requests and handle common errors.
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
        response = requests.request(method, url, headers=headers, json=json_payload, params=params, timeout=timeout)
        response.raise_for_status() 
        if response.status_code == 204 or not response.text:
            return {}
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed to {url}: {e}")
        if e.response is not None:
            print(f"ERROR: Response body: {e.response.text}")
        return None

def get_release_bundle_audit_history(jpd_url, access_token, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory and filters for COMPLETED PROMOTION events.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}"
    params = {"project": project_key}
    audit_data = api_request("GET", api_url, access_token, params=params)

    if audit_data is None:
        return None

    completed_promotions = []
    if "audits" in audit_data and isinstance(audit_data["audits"], list):
        for audit_event in audit_data["audits"]:
            if audit_event.get("subject_type") == "PROMOTION" and audit_event.get("event_status") == "COMPLETED":
                completed_promotions.append(audit_event)
    
    completed_promotions.sort(key=lambda x: x.get('created_millis', 0))
    return completed_promotions

def get_release_bundle_names_with_project_keys(jpd_url, access_token):
    """
    Gets list of release bundles with project key from /lifecycle/api/v2/release_bundle/names.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/release_bundle/names"
    return api_request("GET", api_url, access_token)

def get_release_bundle_versions(jpd_url, access_token, release_bundle_name, project_key="default"):
    """
    Gets list of versions for a specific release bundle name.
    """
    api_url = f"{jpd_url}/lifecycle/api/v2/release_bundle/records/{release_bundle_name}" 
    params = {"project": project_key}
    response_data = api_request("GET", api_url, access_token, params=params)
    if response_data is None:
        return None
    return response_data.get("release_bundles", []) 

def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version, promotion_created_millis, project_key="default"):
    """
    Updates release bundle with a specific timestamp for a promotion record.
    """
    api_url = f"{target_url}/lifecycle/api/v2/promotion/records/{release_bundle}/{bundle_version}?project={project_key}&operation=copy&promotion_created_millis={promotion_created_millis}"
    print(f"Attempting to update promotion record with API: {api_url}")
    return api_request("GET", api_url, access_token)

def parse_repos_to_set(repo_list):
    """
    Converts a list of repositories into a frozenset for order-independent 
    and format-independent comparison. Handles comma-separated strings.
    """
    if not repo_list:
        return frozenset()
    
    parsed_set = set()
    for item in repo_list:
        parsed_set.update(repo.strip() for repo in item.split(','))
    return frozenset(parsed_set)

def main():
    parser = argparse.ArgumentParser(description="Synchronize Release Bundle promotions between two JFrog JPDs.")
    parser.add_argument("sourcetoken", help="Access Token for the Source JPD.")
    parser.add_argument("targettoken", help="Access Token for the Target JPD.")
    parser.add_argument("sourceurl", help="Base URL of the Source JPD.")
    parser.add_argument("targeturl", help="Base URL of the Target JPD.")
    parser.add_argument("environmentfilter", nargs='?', default="", help="Optional: Only sync promotions to this specific environment.")
    parser.add_argument("--project-filter", help="Optional: Only sync release bundles for this specific project key.")

    args = parser.parse_args()
    
    source_access_token = args.sourcetoken
    target_access_token = args.targettoken
    source_url = args.sourceurl
    target_url = args.targeturl
    environment_filter = args.environmentfilter
    project_filter = args.project_filter
    
    print("INFO: Starting Release Bundle Synchronization process.")
    if project_filter:
        print(f"INFO: Project Filter: Only syncing bundles for project '{project_filter}'.")

    # --- Configure JFrog CLI for the Target Server ---
    print("\n--- Configuring JFrog CLI to use the target server ---")
    try:
        print("INFO: Cleaning old JFrog CLI configurations...")
        subprocess.run(["jf", "c", "remove", "--quiet"], check=True)

        print(f"INFO: Configuring target server: {target_url}")
        config_command = [
            "jf", "c", "add", "target-server",
            f"--url={target_url}", f"--access-token={target_access_token}",
            "--interactive=false", "--overwrite"
        ]
        subprocess.run(config_command, check=True, capture_output=True, text=True)
        
        subprocess.run(["jf", "c", "use", "target-server"], check=True)
        print("INFO: JFrog CLI configured successfully.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to configure JFrog CLI: {e.stderr}")
        sys.exit(1)
    
    all_source_rb_names_info = get_release_bundle_names_with_project_keys(source_url, source_access_token)
    if not all_source_rb_names_info or not all_source_rb_names_info.get("release_bundles"):
        sys.exit(0)

    for rb_name_info in all_source_rb_names_info["release_bundles"]:
        current_release_bundle_name = rb_name_info.get("release_bundle_name")
        current_project_key = rb_name_info.get("project_key", "default") 

        if project_filter and current_project_key != project_filter:
            continue

        print(f"\n--- Processing Bundle Name: {current_release_bundle_name} (Project: {current_project_key}) ---")

        all_source_rb_versions_info = get_release_bundle_versions(source_url, source_access_token, current_release_bundle_name, current_project_key)
        if not all_source_rb_versions_info:
            continue

        for rb_version_info in all_source_rb_versions_info:
            current_bundle_version = rb_version_info.get("release_bundle_version")
            if not current_bundle_version:
                continue

            print(f"\n--- Processing Version: {current_release_bundle_name}/{current_bundle_version} ---")
            
            source_promotions = get_release_bundle_audit_history(source_url, source_access_token, current_release_bundle_name, current_bundle_version, current_project_key)
            target_promotions = get_release_bundle_audit_history(target_url, target_access_token, current_release_bundle_name, current_bundle_version, current_project_key)
            
            if source_promotions is None or target_promotions is None:
                continue
            
            def get_promo_signature(promo):
                ctx = promo.get('context', {})
                return (
                    ctx.get('environment'),
                    parse_repos_to_set(ctx.get('included_repository_keys', [])),
                    parse_repos_to_set(ctx.get('excluded_repository_keys', []))
                )

            source_promo_counts = Counter(get_promo_signature(p) for p in source_promotions)
            target_promo_counts = Counter(get_promo_signature(p) for p in target_promotions)

            promotions_to_sync = []
            for promo_sig, source_count in source_promo_counts.items():
                target_count = target_promo_counts.get(promo_sig, 0)
                if source_count > target_count:
                    for promo_event in reversed(source_promotions):
                        if get_promo_signature(promo_event) == promo_sig:
                            for _ in range(source_count - target_count):
                                promotions_to_sync.append(promo_event)
                            break
            
            if not promotions_to_sync:
                print(f"INFO: Target is already in sync for {current_release_bundle_name}/{current_bundle_version}.")
                continue

            print(f"NOTICE: Found {len(promotions_to_sync)} missing promotions to sync.")
            
            for promo_event in promotions_to_sync:
                context = promo_event.get('context', {})
                target_env_for_promo = context.get('environment')
                
                if not target_env_for_promo:
                    print(f"WARNING: Skipping a promotion event because it is missing the 'environment' field.")
                    continue

                promo_inc_repos = context.get('included_repository_keys', [])
                promo_exc_repos = context.get('excluded_repository_keys', [])
                original_promotion_millis = promo_event.get('created_millis')
                
                include_param = f"--include-repos={','.join(promo_inc_repos)}" if promo_inc_repos else ""
                exclude_param = f"--exclude-repos={','.join(promo_exc_repos)}" if promo_exc_repos else ""
                
                jf_command = ["jf", "rbp", current_release_bundle_name, current_bundle_version, target_env_for_promo, f"--project={current_project_key}"]
                if include_param: jf_command.append(include_param)
                if exclude_param: jf_command.append(exclude_param)
                
                print(f"NOTICE: Promoting to {target_env_for_promo}...")
                try:
                    subprocess.run(jf_command, check=True, capture_output=True, text=True)
                    print(f"SUCCESS: Promoted to {target_env_for_promo}.")
                    
                    # Call to update the timestamp after successful promotion
                    if original_promotion_millis:
                        print(f"NOTICE: Updating timestamp for promotion to {target_env_for_promo}...")
                        try:
                            # Add +1 millisecond to the original timestamp before sending the update
                            updated_millis = int(original_promotion_millis) + 1
                        except (ValueError, TypeError):
                            print(f"WARNING: original_promotion_millis '{original_promotion_millis}' is not a valid number. Cannot increment.")
                            updated_millis = original_promotion_millis
                        
                        update_response = update_release_bundle_milliseconds(
                            target_url,
                            target_access_token,
                            current_release_bundle_name,
                            current_bundle_version,
                            updated_millis,
                            current_project_key
                        )
                        if update_response is None:
                            print(f"ERROR: Failed to update timestamp for promotion to {target_env_for_promo}.")
                        else:
                            print(f"SUCCESS: Timestamp updated for {target_env_for_promo}.")
                    else:
                        print(f"WARNING: Skipping timestamp update for {target_env_for_promo}: Original timestamp not available.")

                except subprocess.CalledProcessError as e:
                    print(f"ERROR: Failed to promote to {target_env_for_promo}: {e.stderr}")
                    continue

if __name__ == "__main__":
    main()


# Example 
# python3 sync_rb_promotions.py <source access token> <target access token>   <source jpd url> <target jpd url> "" --project-filter "<project key>"
#  
# python3 sync_rb_promotions.py **** ***   http://172.18.104.154:8082 http://172.18.107.154:8082 "" --project-filter "nd"
