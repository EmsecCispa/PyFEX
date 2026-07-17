# batch_gpt_proxy_openai.py

"""
OpenAI SDK Batch Analyzer for PyPI Packages

- Uses the modern OpenAI Python SDK (OpenAI client).
- Default model: gpt-4o-mini (cost-effective for large analysis).
- Features: Breakpoint resumption, logging, progress tracking, and retry strategies.
- Recommended: Set OPENAI_API_KEY and proxy via environment variables.
"""

import os
import time
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Set

# OpenAI new-style client and exceptions
from openai import OpenAI
from openai import AuthenticationError, RateLimitError, APIError

# ------------------ Logging Configuration ------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pypi_analysis_openai.log"),
        logging.StreamHandler()
    ]
)

# ------------------ Main Analyzer Class ------------------
class OpenAIPyPIAnalyzer:
    def __init__(
        self,
        api_key: str = None,
        results_dir: str = "Results",
        output_dir: str = "Analysis_Results",
        model: str = "gpt-4o-mini",
        proxy_env: dict = None
    ):
        """
        api_key: If None, defaults to OPENAI_API_KEY environment variable.
        proxy_env: Dictionary like {"HTTP_PROXY": "...", "HTTPS_PROXY": "..."}.
                   Best practice is setting these in the OS environment.
        """
        # Optional: Apply proxy settings to environment (use with caution)
        if proxy_env:
            for k, v in proxy_env.items():
                if v:
                    os.environ[k] = v
                    logging.info(f"Set proxy env {k}={v}")

        # Initialize OpenAI client (automatically reads OPENAI_API_KEY from env if api_key is None)
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()
        logging.info(f"OpenAI client initialized using {'provided key' if api_key else 'environment variable'}")

        self.model = model
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.output_dir / "progress.txt"

        # Statistics
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0

        logging.info(f"Analyzer ready. Model={self.model}, input={self.results_dir}, output={self.output_dir}")

    def get_json_files(self) -> List[Path]:
        """Retrieve all JSON metadata files from the results directory."""
        json_files = list(self.results_dir.glob("*.json"))
        logging.info(f"Found {len(json_files)} JSON files in {self.results_dir}")
        return json_files

    def load_progress(self) -> Set[str]:
        """Read progress file to support resuming from a checkpoint."""
        if self.progress_file.exists():
            with open(self.progress_file, "r", encoding="utf-8") as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def save_progress(self, filename: str):
        """Append a processed filename to the progress tracker."""
        with open(self.progress_file, "a", encoding="utf-8") as f:
            f.write(filename + "\n")

    def test_api_connection(self, test_prompt: str = "Say 'hello' only.", timeout: int = 20) -> bool:
        """Quick check to verify OpenAI API connectivity and credentials."""
        logging.info(f"Testing OpenAI connection with model {self.model}...")
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": test_prompt}],
                max_tokens=8,
                temperature=0.0,
                timeout=timeout
            )
            content = resp.choices[0].message.content
            logging.info(f"Connection test OK. Model replied: {str(content).strip()}")
            return True
        except (AuthenticationError, RateLimitError, APIError) as e:
            logging.error(f"API Test Failed: {type(e).__name__} - {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected connection error: {e}")
            return False

    def _build_analysis_prompt(self, package_data: Dict) -> str:
        """Construct the prompt for security analysis."""
        # Clean package data to save tokens
        package_info = {
            "name": package_data.get("name", "unknown"),
            "version": package_data.get("version", "unknown"),
            "files": package_data.get("files", [])[:15], # Show first 15 files
            "file_count": len(package_data.get("files", [])),
        }
# This is just a template; in actual use, it can be adjusted according to the dimension and token consumption rate.
        return f"""
Please analyze this PyPI package for security risks and provide assessment in JSON format only.

Package Data:
{json.dumps(package_info, indent=2)}

Checklist:
- version_mismatch, suspicious_timing, file_type_anomaly, naming_suspicion, code_obfuscation, 
  structure_anomaly, malicious_scripts, metadata_tampering, dependency_confusion.

Return JSON structure:
{{
    "package_name": "string",
    "malicious_score": 0-100,
    "risk_level": "low/medium/high/critical",
    "detection_vectors": ["vector1", "vector2"],
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}
Return ONLY the JSON.
"""

    def analyze_single_package(self, package_json: Dict, retries: int = 3, timeout: int = 60) -> Dict:
        """Call LLM for a single package with retry logic."""
        prompt = self._build_analysis_prompt(package_json)
        sys_msg = {"role": "system", "content": "You are a cybersecurity expert analyzing PyPI malware. Output ONLY valid JSON."}
        user_msg = {"role": "user", "content": prompt}

        for attempt in range(retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[sys_msg, user_msg],
                    temperature=0.1,
                    max_tokens=1000,
                    timeout=timeout,
                    response_format={"type": "json_object"} # Force JSON mode if supported
                )
                
                content_text = resp.choices[0].message.content
                if not content_text:
                    raise ValueError("Empty response")

                # Robust JSON parsing
                try:
                    return json.loads(content_text)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", content_text, re.DOTALL)
                    if match:
                        return json.loads(match.group())
                    raise

            except RateLimitError:
                wait = 2 ** (attempt + 1)
                logging.warning(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logging.warning(f"Attempt {attempt+1} failed for {package_json.get('name')}: {e}")
                time.sleep(1)

        return self._fallback_analysis(package_json)

    def _fallback_analysis(self, package_data: Dict) -> Dict:
        return {
            "package_name": package_data.get('name','unknown'),
            "malicious_score": -1,
            "risk_level": "error",
            "detection_vectors": ["api_failure"],
            "reasoning": "Analysis failed after multiple retries."
        }

    def process_batch(self, delay: float = 1.0):
        """Main loop to process all files in the input directory."""
        if not self.test_api_connection():
            logging.error("OpenAI API connection failed. Aborting.")
            return

        json_files = self.get_json_files()
        processed = self.load_progress()
        remaining = [p for p in json_files if p.name not in processed]
        total = len(remaining)

        logging.info(f"Starting batch: {total} files to process.")
        
        for idx, file_path in enumerate(remaining, start=1):
            try:
                with open(file_path, "r", encoding="utf-8") as rf:
                    pkg = json.load(rf)

                result = self.analyze_single_package(pkg)

                # Save individual result
                out_path = self.output_dir / f"analysis_{file_path.stem}.json"
                with open(out_path, "w", encoding="utf-8") as wf:
                    json.dump(result, wf, indent=2, ensure_ascii=False)

                self.save_progress(file_path.name)
                self.success_count += 1
                
                if idx % 10 == 0 or idx == total:
                    logging.info(f"Progress: {idx}/{total} ({(idx/total)*100:.1f}%)")

                time.sleep(delay)

            except Exception as e:
                logging.error(f"Critical failure on {file_path.name}: {e}")
                self.error_count += 1
            finally:
                self.processed_count += 1

        self.generate_summary_report()

    def generate_summary_report(self):
        """Create a final summary of the batch run."""
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": self.processed_count,
            "success": self.success_count,
            "failed": self.error_count,
            "model": self.model
        }
        with open(self.output_dir / "analysis_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        logging.info(f"Batch complete. Summary: {summary}")

# ------------------ Execution ------------------
def main():
    # User Configuration
    # NOTE: It is highly recommended to NOT hardcode your API Key.
    # Use 'export OPENAI_API_KEY=your_key' in your terminal instead.
    API_KEY = os.environ.get("OPENAI_API_KEY") 
    
    analyzer = OpenAIPyPIAnalyzer(
        api_key=API_KEY,
        results_dir="Results",
        output_dir="Analysis_Results",
        model="gpt-4o-mini"
    )

    try:
        analyzer.process_batch(delay=0.5)
    except KeyboardInterrupt:
        logging.info("Process stopped by user.")

if __name__ == "__main__":
    main()
