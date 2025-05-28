from collections import defaultdict
import requests
import json
import re
from googlesearch import search
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import os


GITHUB_PAT = os.environ.get("PAT")
HUNTER = os.environ.get("HUNTER")
GOOGLE_API = os.environ.get("GOOGLE_API")
GOOGLE_CREDENTIALS_PATH= os.environ.get("PATH_CREDENTIALS")
def get_commits():
    url = "https://api.github.com/repos/vanshb03/New-Grad-2025/commits"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_PAT}",
        'timeout': '500000'
    }
    params = {
        "per_page": 1,
        "page": 1
    }
    response = requests.get(url, headers=headers, params=params)
    commit_shas = []
    for i in response.json():
        commit_shas.append(i['sha'])
    print(commit_shas)
    return commit_shas 
def get_commit_details(commit_sha):
    url = f"https://api.github.com/repos/vanshb03/New-Grad-2025/commits/{commit_sha}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_PAT}",
        "timeout": "500000"
    }
    response = requests.get(url, headers=headers)
    files = response.json().get('files', [])
    domains = []
    for file in files:
        patch = file.get('patch', 'No patch available')
        domains.extend(parse_patch(patch))
    print("commit_details_domains: ", domains)
    return domains
def parse_patch(patch)-> list:
    # print(patch)
    # json_strings = re.findall(r'\+{\+*?}', patch)
    # print(json_strings)
    companies = re.findall(
    r'^\s*\+\s*"company_name"\s*:\s*"([^"]+)"',
    patch,
    re.MULTILINE
    )
    titles = re.findall(
        r'^\s*\+\s*"title"\s*:\s*"([^"]+)"',
        patch,
        re.MULTILINE
    )
    sponsors = re.findall(
        r'^\s*\+\s*"sponsorship"\s*:\s*"([^"]+)"',
        patch,
        re.MULTILINE
    )
    results = [
        {"company_name": c, "title": t, "sponsorship": s}
        for c, t, s in zip(companies, titles, sponsors)
    ]

    domains = []
    for res in results:
        if res["sponsorship"].lower() != "offers sponsorship":
            continue
        company_name = res['company_name']
        query = f"{company_name} official site"
        search_results = search(query, num_results=1)
        search_result = [res for res in search_results]
           
        if search_result:
  
            domain = re.search(r'https?://([^/]+)',search_result[0])
            if domain:
                domains.append((domain.group(1), res['title'], res["company_name"]))

            else:
                print(f"No domain found for {company_name} in search results")
        else:
            print(f"No search results for {company_name}")
    print(domains)
    return domains
def hunter_api(domains):
    print(domains)
    persons = defaultdict(list)

    for domain, title, company_name in domains:
        url = f"https://api.hunter.io/v2/domain-search"
        params = {
            'domain': domain,
            'api_key': HUNTER,
            'company': company_name,
            'department': 'hr,management,engineering',
            'required_filed': 'full_name'       
            }
                    
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'emails' in data['data']:
                emails = data['data']['emails']
                for email_info in emails:
                    email = email_info.get('value')
                    if email:
                        persons[domain].append((email,email_info.get('first_name'), email_info.get('department'), company_name, title))
        else:
            print(f"Error fetching data for {domain}: {response.status_code}")
        outputs = []
        for k, v in persons.items():
            outputs.extend(v)
        return outputs

def gemini_call(title):
    google_api_key = GOOGLE_API
    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = (  "Your task is to select an email subject line based on the provided job title. "
                "Choose from the following options: "
                "1. 'Interested in Machine Learning Engineer New grad role' "
                "2. 'Interested In software engineer new grad role' "
                "3. 'Interested in New Grad Role' "
                "Decision Rules: "
                "- If the job title strongly indicates a Machine Learning, AI, or Data Science role, select option 1."
                "- If the job title strongly indicates a Software Engineering, Software Development, or general programming role (and is not primarily ML/AI/Data Science), select option 2."
                "- For all other cases, or if the role is ambiguous or a general new graduate position (like 'Quantitative Trader', 'Business Analyst', 'Product Manager new grad'), select option 3."
                "Job Title: "f"{title}\n"
                "Respond with ONLY the selected subject line text.")
    response = model.generate_content(prompt)
    print(response.text.strip())
    return response.text.strip()

def google_sheets(persons):

    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet_id = "1QQ3ptppaBKp1i3F-FBqF4rt9uMj5eMr7fr_7nCJV1Mo"
    sheet = client.open_by_key(spreadsheet_id).sheet1
  
    
    for email, name, department, company_name, title in persons:
            subject = gemini_call(title=title)
            sheet.append_row([name, company_name, title, email, subject])
            print(f"Added {email}, {name}, {department}, {company_name}, {title} to Google Sheets")



if __name__ == "__main__":
   commit_sha =  get_commits()
   persons = []
   for sha in commit_sha:
        domains = get_commit_details(sha)
        persons.extend(hunter_api(domains))
   google_sheets(persons)
        
   
      
