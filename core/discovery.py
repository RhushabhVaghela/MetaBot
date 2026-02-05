import os

class ModuleDiscovery:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.capabilities = {}

    def scan(self):
        print(f"Scanning for capabilities in {self.base_path}...")
        # Scan all directories in base_path for skills and kits
        if not os.path.exists(self.base_path):
            print(f"Base path {self.base_path} not found.")
            return

        for item in os.listdir(self.base_path):
            path = os.path.join(self.base_path, item)
            if os.path.isdir(path):
                self.capabilities[item] = path
                print(f"Found capability: {item} at {path}")
                
                # Check for nested skills
                skills_path = os.path.join(path, "skills")
                if os.path.exists(skills_path):
                    found_skills = [
                        d for d in os.listdir(skills_path) 
                        if os.path.isdir(os.path.join(skills_path, d))
                    ]
                    if "skills" not in self.capabilities:
                        self.capabilities["skills"] = []
                    self.capabilities["skills"].extend(found_skills)
                    print(f"Indexed {len(found_skills)} skills from {item}.")

    def get_capability_path(self, name: str):
        return self.capabilities.get(name)
