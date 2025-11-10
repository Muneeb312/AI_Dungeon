import ollama
import json
import os
import re

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
OLLAMA_MODEL = "llama3.1:8b" 
RULES_FILE = os.path.join(SCRIPT_DIRECTORY, "rules.json")
GM_PROMPT_FILE = os.path.join(SCRIPT_DIRECTORY, "prompts", "gm.txt")
SAVE_FILE = os.path.join(SCRIPT_DIRECTORY, "save.json")
TRANSCRIPT_FILE = os.path.join(SCRIPT_DIRECTORY, "samples", "transcript.txt")


def load_json(filename):
    """Loads a JSON file."""
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[ENGINE] Error: Could not parse {filename}. Is it valid JSON?")
        return None

def save_json(filename, data):
    """Saves data to a JSON file."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_txt(filename):
    """Loads a text file."""
    with open(filename, 'r') as f:
        return f.read()

def log_transcript(turn_data):
    """Appends a turn to the transcript file."""
    os.makedirs(os.path.dirname(TRANSCRIPT_FILE), exist_ok=True)
    with open(TRANSCRIPT_FILE, 'a') as f:
        f.write(json.dumps(turn_data) + "\n")

def print_header(state, quest):
    """Prints the game header."""
    print(f"---[ HP: {state['hp']} | Location: {state['location']} | Turn: {state['turns']} ]---")
    print(f"    Quest: {quest['name']} ({quest['goal_flag']})\n")



def call_ollama(system_prompt, rules, state, player_input):
    """
    Calls the Ollama API using the ollama library.
    This does NOT keep chat history. It sends all context every turn.
    """

    user_context = {
        "RULES": rules,
        "STATE": state,
        "LATEST_ACTION": player_input
    }
    

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_context)}
    ]

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            format="json", 
            messages=messages
        )
        
        llm_json_content = json.loads(response['message']['content'])
        return llm_json_content
        
    except json.JSONDecodeError:
        print(f"\n[ENGINE] Error: AI did not return valid JSON.")
        print(f"         Raw response: {response['message']['content']}")
        return None
    except Exception as e:
        print(f"\n[ENGINE] Error communicating with Ollama: {e}")
        return None


def apply_state_changes(state, changes, rules):
    

    if not isinstance(changes, list):
        print(f"\n[ENGINE] AI returned an invalid 'state_change' (expected list, got {type(changes)}). Ignoring.")
        return state

    if not changes:
        return state

    new_state = state.copy()
    inventory = new_state.get('inventory', [])
    flags = new_state.get('flags', {})

    for change in changes:
    
        if not isinstance(change, dict):
            print(f"\n[ENGINE] AI sent invalid atom (expected dict, got {type(change)}). Ignoring: {change}")
            continue 

        atom = change.get("atom")
        
        if atom == "move_to":
            target = change.get("target")
            # RULE CHECK: LOCKS
            if target in rules["LOCKS"]:
                required_flag = rules["LOCKS"][target]
                if required_flag not in flags:
                    print(f"\n[ENGINE] Move to '{target}' blocked. Player lacks flag: '{required_flag}'.")
                    continue 
            new_state["location"] = target

        elif atom == "add_item":
            item = change.get("item")
            if len(inventory) >= rules["INVENTORY_LIMIT"]:
                print(f"\nAdd '{item}' blocked. Inventory full ({rules['INVENTORY_LIMIT']}).")
                continue # Skip this change
            if item not in inventory:
                inventory.append(item)

        elif atom == "remove_item":
            item = change.get("item")
            if item in inventory:
                inventory.remove(item)

        elif atom == "set_flag":
            flag = change.get("flag")
            flags[flag] = True

        elif atom == "hp_delta":
            delta = int(change.get("delta", 0))
            new_state["hp"] += delta
            # Ensure HP doesn't go below 0 here
            if new_state["hp"] <= 0:
                new_state["hp"] = 0
                new_state["flags"]["hp_zero"] = True # Set the lose flag
        
        else:
            print(f"\n[ENGINE] AI tried to use an unknown atom: '{atom}'. Ignoring.")


    new_state['inventory'] = inventory
    new_state['flags'] = flags
    return new_state


def check_end_conditions(state, rules):
    """Checks if a win or lose condition has been met."""
    end_rules = rules["END_CONDITIONS"]
    flags = state["flags"]

    # Check lose conditions
    if state["turns"] >= end_rules["MAX_TURNS"]:
        return "lose", f"You ran out of time! ({end_rules['MAX_TURNS']} turns)"
    
    for flag in end_rules["LOSE_ANY_FLAGS"]:
        if flag in flags:
            return "lose", f"You have met a losing condition: {flag}!"

    # Check win conditions
    win_flags_met = all(flag in flags for flag in end_rules["WIN_ALL_FLAGS"])
    if win_flags_met:
        return "win", "You have won the game! Congratulations!"

    return None, None

def print_help(rules):
    """Prints commands."""
    print("\n--- Help ---")
    print("Type what you want to do (e.g., 'look at the chest', 'go to the forest').")
    print("\nEngine commands:")
    print("  help        - Show this message")
    print("  inventory   - Check your items")
    print("  save        - Save your game")
    print("  load        - Load your last save")
    print("  quit        - Exit the game")
    print("------------")

def print_inventory(state):
    """Prints the player's inventory."""
    print("\n--- Inventory ---")
    if not state["inventory"]:
        print("  (empty)")
    else:
        for item in state["inventory"]:
            print(f"  * {item}")
    print("-----------------")


def main():
    
    try:
        rules = load_json(RULES_FILE)
        gm_prompt = load_txt(GM_PROMPT_FILE)
    except FileNotFoundError as e:
        print(f"Error: Missing required file: {e.filename}")
        print("Please make sure 'rules.json' and 'prompts/gm.txt' exist in the same folder as main.py.")
        return
    except TypeError:
        if not rules:
            print(f"Error: Could not find 'rules.json' at {RULES_FILE}.")
            return
        if not gm_prompt:
             print(f"Error: Could not find 'prompts/gm.txt' at {GM_PROMPT_FILE}.")
             return


    state = load_json(SAVE_FILE)
    if state:
        print("... Game loaded from save. ...")
    else:
        print("... Starting new game. ...")
        state = rules["START"].copy() 
        state["turns"] = 0
    
    quest = rules["QUEST"]
    print(f"\nQuest: {quest['name']}")
    print(quest['intro'])

    while True:
        # Check End Conditions 
        status, message = check_end_conditions(state, rules)
        if status:
            print(f"\n--- GAME OVER: YOU {status.upper()}! ---")
            print(message)
            break

        # Display Status & Get Input
        print_header(state, quest)
        try:
            player_input = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            player_input = "quit" 

        if not player_input:
            continue

        if player_input == "quit":
            print("Goodbye Traveller!")
            break
        elif player_input == "save":
            save_json(SAVE_FILE, state)
            print("... Game saved. ...")
            continue 
        elif player_input == "load":
            loaded_state = load_json(SAVE_FILE)
            if loaded_state:
                state = loaded_state
                print("... Game loaded. ...")
            else:
                print("... No save file found. ...")
            continue 
        elif player_input == "help":
            print_help(rules)
            continue
        elif player_input == "inventory":
            print_inventory(state)
            continue 

        state["turns"] += 1
        
        llm_response = call_ollama(gm_prompt, rules, state, player_input)


        # Log Results
        narration = llm_response.get("narration", "(The AI provided no narration.)")
        changes = llm_response.get("state_change", [])
        log_transcript({
            "turn": state["turns"],
            "input": player_input,
            "llm_response": llm_response
        })
        
        state = apply_state_changes(state, changes, rules)

        paragraphs = re.split(r'\n\s*\n', narration)
        trimmed_narration = "\n\n".join(paragraphs[:rules["MAX_PARAGRAPHS"]])
        
        print(f"\n{trimmed_narration}")


if __name__ == "__main__":
    main()