import time
import requests
import traceback

BASE_URL = "http://localhost:8000/api"

# Local tracking to avoid spamming the backend
last_parse_times = {}

def job_auto_parse(project_id):
    print(f"[{project_id}] Checking Auto-Parse...")
    try:
        res = requests.post(f"{BASE_URL}/news/fetch", headers={"X-Project-Id": str(project_id)})
        if res.status_code == 200:
            added = res.json().get("added", 0)
            if added > 0:
                print(f"[{project_id}] Auto-Parse added {added} news.")
    except Exception as e:
        print(f"[{project_id}] Auto-Parse error: {e}")

def job_auto_generate(project_id):
    print(f"[{project_id}] Checking Auto-Generate...")
    try:
        # Trigger Media Assembly for tasks that are waiting in NEW state in the Queue
        res_queue = requests.get(f"{BASE_URL}/queue", headers={"X-Project-Id": str(project_id)})
        if res_queue.status_code == 200:
            tasks = res_queue.json()
            for task in tasks:
                if task.get("status") == "NEW":
                    # Task is in queue, text is generated, wait for assembly
                    # Make sure the prompt isn't the placeholder
                    if "Ожидаем текст..." not in str(task.get("prompt")):
                        print(f"[{project_id}] Auto-Assembling media for task: {task['video_title']}")
                        requests.post(f"{BASE_URL}/queue/{task['task_id']}/generate_media", headers={"X-Project-Id": str(project_id)})
                        time.sleep(5)
    except Exception as e:
        print(f"[{project_id}] Auto-Generate error: {e}")

def job_auto_publish(project_id):
    print(f"[{project_id}] Checking Auto-Publish...")
    try:
        res = requests.get(f"{BASE_URL}/ready", headers={"X-Project-Id": str(project_id)})
        if res.status_code == 200:
            tasks = res.json()
            for task in tasks:
                if task.get("file_exists") and task.get("status") == "READY":
                    print(f"[{project_id}] Auto-Publishing task: {task['video_title']}")
                    requests.post(f"{BASE_URL}/queue/{task['task_id']}/upload", headers={"X-Project-Id": str(project_id)})
                    time.sleep(10) # Wait a bit between firing background upload tasks
    except Exception as e:
        print(f"[{project_id}] Auto-Publish error: {e}")


def main_loop():
    print("========================================")
    print("Scheduler daemon started.")
    print("========================================")
    
    while True:
        try:
            # Ping backend to indicate daemon is alive
            try:
                requests.post(f"{BASE_URL}/scheduler/ping", timeout=5)
            except Exception:
                pass
                
            # 1. Fetch all projects
            try:
                projects_res = requests.get(f"{BASE_URL}/projects", timeout=10)
                if projects_res.status_code != 200:
                    time.sleep(10)
                    continue
                projects = projects_res.json()
            except requests.exceptions.RequestException:
                print("Backend not running. Waiting...")
                time.sleep(15)
                continue
                
            for project in projects:
                p_id = project["id"]
                
                # 2. Fetch Global Settings for this project
                settings_res = requests.get(f"{BASE_URL}/settings", headers={"X-Project-Id": str(p_id)})
                if settings_res.status_code != 200:
                    continue
                settings = settings_res.json()
                
                auto_parse = settings.get("auto_parse") == "true"
                auto_generate = settings.get("auto_generate") == "true"
                auto_publish = settings.get("auto_publish") == "true"
                
                now = time.time()
                
                # --- Auto Parse ---
                # Check every 30 minutes (1800 seconds)
                if auto_parse:
                    last_parse = last_parse_times.get(p_id, 0)
                    if now - last_parse > 1800:
                        job_auto_parse(p_id)
                        last_parse_times[p_id] = now
                        
                # --- Auto Generate ---
                if auto_generate:
                    job_auto_generate(p_id)
                    
                # --- Auto Publish ---
                if auto_publish:
                    job_auto_publish(p_id)
                    
        except Exception as e:
            print(f"Scheduler loop error: {e}")
            traceback.print_exc()
            
        # Global wait before next loop tick
        print("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
