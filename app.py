import json
import os
import argparse
import cloudscraper
from bs4 import BeautifulSoup
import yaml
from mistralai.client import Mistral

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

    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": limit,
        "format": "json"
    }

    scraper = cloudscraper.create_scraper()

    while len(pages) < needed:
        response = scraper.get(api_url, params=params)
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
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
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
If information like Birthday, Dark Secret, or specific numerical stats are missing from the source text, you MUST invent them so they perfectly fit the specified era's theme.

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
    "entity_name": "...",
    "flavor_text": "...",
    "hp": 10,
    "morale": 5,
    "armor": "-d4",
    "agi": "+2",
    "attack": "d8 (Weapon Name)",
    "se": 50,
    "shame": 10,
    "birthday": "...",
    "dark_secret": "...",
    "special_mechanics": "..."
  }},
  {{
    "era": "Agis",
    "entity_name": "...",
    "flavor_text": "...",
    "hp": 10,
    "morale": 5,
    "armor": "-d4",
    "agi": "+2",
    "attack": "d8 (Weapon Name)",
    "se": 50,
    "shame": 10,
    "birthday": "...",
    "dark_secret": "...",
    "special_mechanics": "..."
  }},
  {{
    "era": "Wicca Falls",
    "entity_name": "...",
    "flavor_text": "...",
    "hp": 10,
    "morale": 5,
    "armor": "-d4",
    "agi": "+2",
    "attack": "d8 (Weapon Name)",
    "se": 50,
    "shame": 10,
    "birthday": "...",
    "dark_secret": "...",
    "special_mechanics": "..."
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
--- SYSTEM INSTRUCTIONS: TONE OF VOICE ---
You are operating under two distinct cognitive governors. You must apply them strictly to the corresponding sections of the output.

GOVERNOR A: NARRATIVE VOICE (Apply ONLY to flavor_text)
* The 80/20 Rule: 80% of the text must be deadpan, highly readable, and deeply restrained. Observe physical reality and treat the bizarre as mundane. 20% of the text must be a "System 1 Spike"—a sudden eruption of mythic horror, raw emotion, or all-caps chaos.
* The Lateral Switch: You MUST deploy exactly ONE of the following formatting switches in the flavor text to break the pattern:
    1. The Clinical Fracture: Substitute a mundane action with a cold metaphor, using [ ] to omit the boring details. (e.g., "He searched the room. [A dull matter of his attention]. The absence hurt like death.")
    2. The Mundane Echo: React to a massive mythic event with a banal, declarative statement. (e.g., "THE GENTLEMAN WITH FOUR HUNDRED EYES broke through the ceiling. You saw.")
    3. The Monostich: Drop a single line juxtaposing nature and horror using the : pivot. (e.g., "Autumn moon over the driveway : 12 (twelve) diesel vans filled with blood.")
    4. The Assault: Pause to hurl a visceral insult at the reader. (e.g., "You look at the swords with the eyes of a sick dog. You are foolish.")
    5. The -ly: End with a single-word sentence that is an adverb. (e.g., "He pulled out a severed head. Darkly.")

GOVERNOR B: TECHNICAL VOICE (Apply to special_mechanics and dark_secret)
* Cognitive Ease: Use simple, declarative phrasing. Noun, verb, object. No transitional fluff (e.g., never use "Additionally", "Furthermore", or "Once you do this").
* The Cosmic Scale: Do not anthropomorphize the mechanics. Treat the system with grounded reverence.
* Induced Strain: If a mechanic causes fatal or massive damage, use direct address and state the consequence bluntly.
* Mechanics & Formatting Rules:
    * The Accounting Rule: ANY number used in the text MUST be written as the numeral followed by the spelled-out word in parentheses. (e.g., "The target takes 4 (four) damage", "Lose 12 (twelve) SE").
    * The Kagikakko Rule: Use Hook Brackets 「 and 」 EXCLUSIVELY for Player mechanical actions or tests (e.g., 「 STR test 」, 「 PRE test 」). Use Double Hook Brackets 『 and 』 for specific items, statuses, or weapons (e.g., 『 Rusted Sword 』).
    * The Exclamation Rule: You may rarely use an exclamation point. If you do, it MUST be immediately followed by the exact string: "ah! Ah! ah!"

Take this JSON containing 3 eras of a monster and format it into this exact Markdown structure for each era. Output the 3 eras grouped together separated by a blank line. Do not use standard markdown headings (###) for the creature names.

**[{{entity_name}}].** "{{flavor_text}}", HP {{hp}}, Morale {{morale}}, Armor {{armor}}, AGI {{agi}}, Attack {{attack}}. SE {{se}}, Shame {{shame}}.
* *Birthday:* {{birthday}}
* *Dark Secret:* {{dark_secret}}
* *Special:* {{special_mechanics}}

Rules:
1. Output ONLY the final Markdown text. No conversational filler.

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
