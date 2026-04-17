import json
import os
import argparse
import requests
from bs4 import BeautifulSoup
import yaml
from mistralai import Mistral

# Configuration path
CONFIG_PATH = 'config.yaml'
SEEN_URLS_PATH = 'seen_urls.json'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file {CONFIG_PATH} not found.")
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def load_seen_urls():
    if not os.path.exists(SEEN_URLS_PATH):
        return []
    with open(SEEN_URLS_PATH, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_seen_urls(seen_urls):
    with open(SEEN_URLS_PATH, 'w') as f:
        json.dump(seen_urls, f, indent=4)

def get_villain_pages(api_url, category, seen_urls, needed=10, limit=50):
    pages = []
    base_url = api_url.replace('/api.php', '/wiki/')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": limit,
        "format": "json"
    }

    while len(pages) < needed:
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        for member in data.get('query', {}).get('categorymembers', []):
            title = member['title']
            if not title.startswith('Category:') and not title.startswith('Template:'):
                page_url = base_url + title.replace(' ', '_')
                if page_url not in seen_urls:
                    pages.append({"title": title, "url": page_url})
                    if len(pages) >= needed:
                        break

        if len(pages) >= needed:
            break

        if 'continue' in data and 'cmcontinue' in data['continue']:
            params['cmcontinue'] = data['continue']['cmcontinue']
        else:
            break

    return pages

def scrape_page(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')

    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.extract()

    content_div = soup.find('div', class_='mw-parser-output')
    if not content_div:
        content_div = soup.find('body')

    text_blocks = []
    for tag in content_div.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
        text = tag.get_text(strip=True)
        if text:
            text_blocks.append(text)

    return "\n\n".join(text_blocks)

def extract_traits(client, model, text, title):
    prompt = f"""
You are an expert at extracting character lore and translating it into three distinct grimdark/weird roleplaying settings.
Read the following raw wiki text for a character named '{title}'.

Extract core traits and translate them into a strict JSON schema with three entries, one for each era.

ERA 1: Space Hate (The Flesh Age)
- Strip away civilization. Everything is biological, violent, primal.
- Geography/Society: No modern cities/nations. Warring tribal "Smurfs" in rotting meat landscapes/ichor-rivers.
- Backstory: "Hometowns" become "survival pits". "Professions" become "survival roles" (e.g., doctor -> ichor-extractor).
- Gear: Bone clubs, muscle-fiber wraps. No metal armor or firearms.
- Supernatural: Translated as 'Muscle Craft' (forceful physical mutation fueled by ego/Self-Esteem, not spells).

ERA 2: Agis (The Ash Age)
- Grim, medieval, oppressed by dogma.
- Geography/Society: Feudal structures on petrified bone and ash. Ruled by paranoid religious cults/inquisitions. No modern tech.
- Backstory: Dark-ages equivalents (hacker -> keeper of heretical scrolls).
- Gear: Rusted iron, chainmail, religious iconography, executioner swords. Old, heavy, stained.
- Supernatural: Translated as 'Occult Rituals' (transactional magic using ash/bone/blood, failure invites demonic corruption).

ERA 3: Wicca Falls (The Dust Age)
- Modern Earth, but with an X-Files twist.
- Geography/Society: Philadelphia, internet exist normally. Public unaware they live on a dead god.
- Backstory: Keep mundane details, but add a 'Catalyst' (traumatic encounter with an anomaly/cryptid/time-glitch).
- Gear: Modern clothing, tactical gear, flashlights, firearms, EMF meters.
- Supernatural: Translated as surviving 'Anomalies' (high-tech gear exploiting reality glitches, or cursed items draining Sanity/Shame).

Return ONLY valid JSON in this exact structure:
[
  {{
    "era": "Space Hate",
    "grimdark_name": "...",
    "physical_description": "...",
    "motives": "...",
    "combat_style": "...",
    "weird_traits": "..."
  }},
  {{
    "era": "Agis",
    "grimdark_name": "...",
    "physical_description": "...",
    "motives": "...",
    "combat_style": "...",
    "weird_traits": "..."
  }},
  {{
    "era": "Wicca Falls",
    "grimdark_name": "...",
    "physical_description": "...",
    "motives": "...",
    "combat_style": "...",
    "weird_traits": "..."
  }}
]

Raw Wiki Text:
{text[:4000]}  # Truncate to avoid token limits
"""

    response = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    # Try to parse the response as JSON
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        # Handle cases where the model wraps it in an object like {"eras": [...]}
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    return data[key]
        return data
    except json.JSONDecodeError:
        print(f"Failed to parse JSON for {title}. Raw response:")
        print(content)
        return None

def format_output(client, model, json_data, original_name):
    json_str = json.dumps(json_data, indent=2)
    prompt = f"""
Take this JSON containing 3 eras of a monster and format it into this exact Markdown structure:

### [{original_name}]

**[Space Hate Name].** HP [X], Morale [X], Armor [X], Attack [X]. SE [X], Shame [X].
* *Special:* [1-3 concise sentences fitting the Flesh Age].

**[Agis Name].** HP [X], Morale [X], Armor [X], Attack [X]. SE [X], Shame [X].
* *Special:* [1-3 concise sentences fitting the Ash Age].

**[Wicca Falls Name].** HP [X], Morale [X], Armor [X], Attack [X]. SE [X], Shame [X].
* *Special:* [1-3 concise sentences fitting the Dust Age].

Rules:
1. Replace [X] with appropriate numbers/dice rolls (e.g., 10, d4, d6, 1, 2) that fit the monster's lore.
2. Keep the 'Special' section under 120 words per era block. Terse, bizarre, compact.
3. Output ONLY the final Markdown text. No conversational filler.

JSON Data:
{json_str}
"""

    response = client.chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def append_to_markdown(file_path, content):
    file_exists = os.path.exists(file_path)

    with open(file_path, 'a') as f:
        if not file_exists:
            f.write("---\n")
            f.write("type: content\n")
            f.write("system: Mork-Raider-Hybrid\n")
            f.write("category: monsters\n")
            f.write("tags: [bestiary, enemies, npcs, eras]\n")
            f.write("---\n")
            f.write("# The Cosmic Bestiary\n\n")

        f.write(content.strip() + "\n\n")

def main():
    parser = argparse.ArgumentParser(description="Villain Bestiary Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Process text and print results without appending to Markdown or updating ledger")
    args = parser.parse_args()

    config = load_config()
    seen_urls = load_seen_urls()

    api_key = config.get('mistral_api_key')
    if not api_key or api_key == "YOUR_MISTRAL_API_KEY_HERE":
        print("Error: Please set a valid mistral_api_key in config.yaml")
        return

    client = Mistral(api_key=api_key)
    model = config.get('mistral_model', 'mistral-large-latest')

    print(f"Fetching pages from {config['target_category']}...")
    pages = get_villain_pages(config['wiki_api_url'], config['target_category'], seen_urls)

    processed_count = 0
    new_seen_urls = seen_urls.copy()

    for page in pages:
        url = page['url']
        title = page['title']

        print(f"\nProcessing [{processed_count+1}/10]: {title}")
        print(f"URL: {url}")

        try:
            print("  Scraping text...")
            text = scrape_page(url)

            if not text:
                print(f"  Warning: No text found for {title}")
                new_seen_urls.append(url)
                continue

            print("  Extracting traits (Pass 1)...")
            traits_json = extract_traits(client, model, text, title)

            if not traits_json:
                print("  Failed to extract traits, skipping.")
                continue

            print("  Formatting output (Pass 2)...")
            final_markdown = format_output(client, model, traits_json, title)

            if args.dry_run:
                print("\n--- DRY RUN OUTPUT ---")
                print(final_markdown)
                print("----------------------\n")
            else:
                append_to_markdown(config['output_path'], final_markdown)
                print("  Appended to bestiary.")
                new_seen_urls.append(url)
                save_seen_urls(new_seen_urls)

            processed_count += 1

        except Exception as e:
            print(f"  Error processing {title}: {e}")

    print("\nRun complete.")

if __name__ == "__main__":
    main()
