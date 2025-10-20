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
    formerMembers = []
    currentMembers = []
    calendarDetails = []
    logEntries = []
    addonSettings = []
    playerListAlts = []
    guildDataBackup = []
    restoreMembers = []
    restoreFormerMembers = []
    restoreLog = []
    miscSettings = []
    altsList = []
    dailyAnnouncements = []

    saveTables = [
        "GRM_GuildMemberHistory_Save = {" , # Starting at 2nd save variable as first is auto in position
        "GRM_CalendarAddQue_Save = {",
        "GRM_LogReport_Save = {",
        "GRM_AddonSettings_Save = {",
        "GRM_PlayerListOfAlts_Save = {",
        "GRM_GuildDataBackup_Save = {",
        "GRM_Restore_Members = {",
        "GRM_Restore_FormerMembers = {",
        "GRM_Restore_Log = {",
        "GRM_Misc = {",
        "GRM_Alts = {",
        "GRM_DailyAnnounce = {"
    ]
    # We only need logReport (index 3) for the parser function later
    SeparatedTables = [ formerMembers , currentMembers , calendarDetails, logEntries ,
                        addonSettings , playerListAlts , guildDataBackup ,
                        restoreMembers , restoreFormerMembers , restoreLog ,
                        miscSettings , altsList , dailyAnnouncements ]

    # 3. Separate Tables (Only up to GRM_Misc, index 6, is needed to capture LogReport)
    currentArray = []
    saveTableIndex = 0
    separatedTablesIndex = 0


    for i, line in enumerate(data):

        if saveTables[saveTableIndex] in line:
            SeparatedTables[separatedTablesIndex] = copy.deepcopy(currentArray)
            currentArray = []
            separatedTablesIndex += 1
            if saveTableIndex < len(saveTables) - 1:
                saveTableIndex += 1

        currentArray.append ( line )

        if i == len(data):
            SeparatedTables[separatedTablesIndex] = copy.deepcopy(currentArray)

    # 4. Parse Log Report Table
    final_log_data = ParseLog(SeparatedTables[3])

    # Let's sort the data now by number of entries per guild, descending.
    sorted_items = sorted(
        final_log_data.items(),
        key=lambda item: len(item[1]),
        reverse=True
    )
    # Rebuild the dictionary from the sorted list of items.
    sorted_log_data = {guild: logs for guild, logs in sorted_items}

    return sorted_log_data

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
    opening_pattern = r"(^\s*{\s*$|=\s*{\s*$)"
    closing_pattern = r"^\s*},\s*$"
    entryIndex = 0
    cleanLine = ""
    totalEntries = 0

    for i,line in enumerate(data[1:], start=1): # Skipping the first line which is the table opening

        # 1. Detect Guild Name (["Guild Name"] = {)
        if bracketCount == 0 and re.search ( namePattern , line ):
        # if re.search ( namePattern , line ):
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
                totalEntries += 1

        # 3. Bracket Counting for Structure
        if re.search ( opening_pattern , line ):
            bracketCount += 1

        elif re.search ( closing_pattern , line ):
            bracketCount -= 1

            if bracketCount == 2:
                # End of a single log entry sub-table
                entryIndex = 0

            elif bracketCount == 1:
                bracketCount = 0
                totalEntries = 0

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
    """Formats the log data dictionary into a two-column CSV string: Guild Name and Log Entry."""
    output = StringIO()
    # Ensure UTF-8 BOM for proper Excel handling of special characters
    output.write('\ufeff')
    writer = csv.writer(output)

    # Column names
    writer.writerow(["Guild Name", "Log Entry"])

    # Loop through the data and write the full log entry in the second column
    for guild_name, entries in log_data.items():
        for entry in entries:
            writer.writerow([guild_name, entry])

    return output.getvalue()
