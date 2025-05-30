from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import requests
import json
import re
from googlesearch import search
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import os
from datetime import datetime, timedelta


GITHUB_PAT = os.environ.get("PAT")
HUNTER = os.environ.get("HUNTER")
GOOGLE_API = os.environ.get("GOOGLE_API")


# def send_notification_email():
#     """Send notification email when no new jobs are available"""
#     try:
#         msg = MIMEMultipart()
#         msg['From'] = "tyalaman03@gmail.com"
#         msg['To'] = "tejasrocks1234567890@gmail.com"
#         msg['Subject'] = "No New Jobs Available Today"
        
#         body = f"""
#         Hello,
        
#         The job scraping process has completed for {datetime.now().strftime('%Y-%m-%d')}.
        
#         No new jobs were found today - all discovered positions already exist in your spreadsheet.
        
#         Best regards,
#         Job Scraper Bot
#         """
        
#         msg.attach(MIMEText(body, 'plain'))
        
#         server = smtplib.SMTP('smtp.gmail.com', 587)
#         server.starttls()
#         server.login(G, GMAIL_PASSWORD)
#         text = msg.as_string()
#         server.sendmail(GMAIL_EMAIL, GMAIL_EMAIL, text)
#         server.quit()
        
#         print("Notification email sent successfully!")
        
#     except Exception as e:
#         print(f"Failed to send notification email: {e}")
 
scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
credentials = Credentials.from_service_account_file(
        "credentials.json", scopes=scopes)
client = gspread.authorize(credentials)
spreadsheet_id = "1QQ3ptppaBKp1i3F-FBqF4rt9uMj5eMr7fr_7nCJV1Mo"
sheet = client.open_by_key(spreadsheet_id).sheet1
def get_existing_emails(sheet):
    """Get all existing emails from the Google Sheet"""
    try:
        all_records = sheet.get_all_records()
        existing_emails = set()
        for record in all_records:
            #email = record.get('Email', '').strip()  # Adjust column name as needed
            company  = record.get('Company', '').strip()  # Adjust column name as needed
            title = record.get('Role', '').strip()  # Adjust column name as needed
            if company and title:
                existing_emails.add((company.lower(), title.lower()))

        return existing_emails
    except Exception as e:
        print(f"Error getting existing emails: {e}")
        return set()
def get_commits():
    url = "https://api.github.com/repos/vanshb03/New-Grad-2025/commits"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_PAT}",
        'timeout': '500000'
    }
    current_date = datetime.now()
    two_days_ago = current_date - timedelta(days=2)
    
    # Format dates in ISO 8601 format (required by GitHub API)
    since_date = two_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "per_page": 300,
        "page": 1,
        'since': since_date,
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
    existing = get_existing_emails()
    for file in files:
        patch = file.get('patch', 'No patch available')
        domains.extend(parse_patch(patch, existing))
    print("commit_details_domains: ", domains)
    return domains
def parse_patch(patch, existing)-> list:
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
        key = (res['company_name'].strip().lower(), res['title'].strip().lower())
        if res["sponsorship"].lower() != "offers sponsorship" or key in existing:
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

   
  
    
    for email, name, department, company_name, title in persons:
            subject = gemini_call(title=title)
            sheet.append_row([name, company_name, title, email, subject])
            print(f"Added {email}, {name}, {department}, {company_name}, {title} to Google Sheets")



if __name__ == "__main__":
   commit_sha =  get_commits()
   persons = []
   for sha in commit_sha:
        domains = get_commit_details(sha)
        if domains is None or len(domains) == 0:
            continue
        persons.extend(hunter_api(domains))
   google_sheets(persons)
        
   
      
