# IMPORTS
import copy
import re
import json
from io import StringIO
import csv

# ======================================================================
# CORE PARSING ENTRY POINT
# ======================================================================

def process_lua_content(lua_content: str) -> dict:
    """
    Takes the raw string content of the LUA file, extracts the log report table,
    and returns the structured log data dictionary.
    """
    # 1. Prepare data lines
    # splitlines(keepends=True) ensures that the line ending structure is maintained
    # for consistent table boundary detection (like the original readlines() behavior).
    data = lua_content.splitlines(keepends=True)

    # 2. Define Save Table Boundaries (Required for finding LogReport)
    leftPlayers = []
    currentMembers = []
    logReport = []
    settings = []
    alts = []
    backupData = []

    saveTables = [
        "GRM_GuildMemberHistory_Save = {" ,
        "GRM_CalendarAddQue_Save = {" ,
        "GRM_LogReport_Save = {" ,       # Index 2 (Log Report)
        "GRM_AddonSettings_Save = {" ,
        "GRM_PlayerListOfAlts_Save = {" ,
        "GRM_GuildDataBackup_Save = {" ,
        "GRM_Misc = {" ,
        "GRM_Alts = {" ,
        "GRM_DailyAnnounce = {"
    ]
    # We only need logReport (index 3) for the parser function later
    SeparatedTables = [ leftPlayers , currentMembers , None , logReport , settings , None , backupData , None , alts ]

    # 3. Separate Tables (Only up to GRM_Misc, index 6, is needed to capture LogReport)
    currentArray = []
    currentSaveIndex = 0

    for line in data:
        currentArray.append ( line )

        if currentSaveIndex < len(saveTables) and saveTables[currentSaveIndex] in line:

            if currentSaveIndex == 2:
                # Capture the lines that follow the LogReport start definition
                SeparatedTables[3] = copy.deepcopy(currentArray)

            currentArray = []
            currentSaveIndex += 1

        if currentSaveIndex >= 6:
            # Stop parsing after GRM_GuildDataBackup_Save / before GRM_Misc
            break

    # 4. Execute the Log Parsing
    if not SeparatedTables[3]:
        # Handle case where Log Report table was empty or not found
        return {}

    final_log_data = ParseLog(SeparatedTables[3])

    return final_log_data

# ======================================================================
# LOG PARSING FUNCTIONS (Modified to remove prints)
# ======================================================================

def remove_string_coloring(text: str) -> str:
    """
    Removes Blizzard-style hex coloring tags (|cffXXXXXX) and color reset tags (|r, |R)
    from a string, and truncates at the first null character (\000).
    """
    text = fix_corrupted_unicode(text)
    text = re.split(r'\x00', text, 1)[0]
    color_pattern = r'\|c[0-9A-Fa-f]{6,8}|\|r'
    text = re.sub(color_pattern, '', text, flags=re.IGNORECASE)
    return text

def fix_corrupted_unicode(text):
    """Reverses the common UTF-8 -> Latin-1 corruption pattern."""
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

def ParseLog ( data ):
    LogData = {}
    namePattern = r'\[\"(.*)\"\]'
    bracketCount = 0
    opening = "{\n"
    closing = "},\n"
    entryIndex = 0
    cleanLine = ""

    for line in data:

        # 1. Detect Guild Name (e.g., ["Guild Name"] = {)
        if bracketCount == 0 and re.search ( namePattern , line ):
            name = re.search ( namePattern , line ).group(1)
            bracketCount += 1
            LogData[name] = []

        # 2. Detect Log Entry Value (3rd level bracket count)
        elif bracketCount == 3:
            entryIndex += 1
            if entryIndex == 2:
                # This is the line containing the actual log string value
                cleanLine = line.strip().rstrip(',')

                if cleanLine.startswith('"') and cleanLine.endswith('"'):
                    cleanLine = cleanLine[1:-1]

                cleanLine = cleanLine.replace("\\n" , " ")
                cleanLine = cleanLine.replace('\\"', '"')
                cleanLine = remove_string_coloring(cleanLine)

                LogData[name].append(cleanLine)

        # 3. Bracket Counting for Structure
        if re.search ( opening , line ):
            bracketCount += 1

        elif re.search ( closing , line ):
            bracketCount -= 1

            if bracketCount == 2:
                # End of a single log entry sub-table
                entryIndex = 0

            elif bracketCount == 1:
                # End of a Guild's log history table
                bracketCount = 0

    return LogData

# ======================================================================
# EXPORT FORMATTING FUNCTIONS
# ======================================================================

def format_to_text(log_data: dict) -> str:
    """Formats the log data dictionary into a simple, human-readable text output."""
    output = []
    for guild_name, entries in log_data.items():
        output.append("=" * 60)
        output.append(f"Guild: {guild_name} ({len(entries)} entries)")
        output.append("=" * 60)
        output.extend(entries)
        output.append("\n") # Blank line spacer
    return "\n".join(output)

def format_to_csv(log_data: dict) -> str:
    """Formats the log data dictionary into a CSV string."""
    # Use StringIO to simulate a file for the CSV writer
    output = StringIO()
    # Ensure UTF-8 BOM for proper Excel handling of special characters
    output.write('\ufeff')
    writer = csv.writer(output)

    writer.writerow(["Guild Name", "Date/Time", "Log Entry"])

    # Pattern to grab the date/time stamp
    # Format example: "28 Nov '23 01:19pm : Arkaan has Come ONLINE..."
    date_pattern = r'^(\d{1,2} \w{3} \'\d{2} \d{1,2}:\d{2}(?:am|pm)\s*:\s*)(.*)$'

    for guild_name, entries in log_data.items():
        for entry in entries:
            match = re.match(date_pattern, entry)

            if match:
                # Group 1 is the timestamp (with trailing colon)
                timestamp = match.group(1).strip().rstrip(':').strip()
                # Group 2 is the rest of the message
                message = match.group(2).strip()
            else:
                # If the log entry format doesn't match the expected timestamp pattern
                timestamp = "N/A"
                message = entry

            writer.writerow([guild_name, timestamp, message])

    return output.getvalue()
