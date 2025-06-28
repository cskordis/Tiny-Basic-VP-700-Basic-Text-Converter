# TextToWavVIPFileCLI version 1.0
# Author : Costas Skordis
# Thank you to Marcel van Tongeren in helping me decipher the block structure using his EMMA 02 emulator
# June 2025

# Requires Python 3.1.2 or newer

"""
Takes the contents of a text file in basic and encodes it into a Kansas
City Standard WAV file, that when played will upload data via the
cassette tape input on the Cosmac ELF II Full Basic Math computers.

The format of the data is the following:

Bit 1 is represented by 800 Hz
Bit 0 is represented by 2000 Hz
There is a leader sequence of 2000Hz Bit 0 for about 8 seconds before the data.
The data block is a start bit of 1, followed by the byte representing the character and then and even parity bit.

        
Byte 0      High Byte Ascii Total
Byte 1      Low  Byte Ascii Total       
Byte 2      Length High Byte
Byte 3      Length Low Byte
Byte 4 - 9  Zero Byte sequence
Byte 10     High Byte of Line Label        
Byte 11     Low Byte of Line Label
Byte 12     Line length in bytes with no spaces
Byte 13     BASIC code with terminating carriage return

       
                ______________________________________________________
_______________|                                                    |Repeated as many as there are characters in code 
|Leader 8 secs |Ascii Total Sum   |Sum of all      |zero bytes      |Line Label |Number of code characters|Code|Carriage Return|
|@ 2000Hz      |from Byte 3 as hex|basic character |repeated 6 times|2 Bytes    |of line (no spaces)      |Byte|               |


See http://en.wikipedia.org/wiki/Kansas_City_standard
"""


# A few global parameters related to the encoding

FRAMERATE = 22050      # Hz
ONES_FREQ = 800        # Hz (per KCS)
ZERO_FREQ = 2000       # Hz (per KCS)
AMPLITUDE = 225        # Amplitude of generated square waves
CENTER    = 128        # Center point of generated waves
LEADER    = 8          # Default seconds for leader
PARITY    = 0          # Parity 0 = Odd, 1 = Even
STARTBIT  = 1          # Start Bit
BLANKS    = 25         # Number of single one pulses at the very end of the file

# Create nmemonic shortcuts
mnemonic_index = {}
mnemonic_index["?"]="88"
mnemonic_index["ABS"]="9C"
mnemonic_index["CLS"]="9C"
mnemonic_index["COLOR"]="A4"
mnemonic_index["END"]="94"
mnemonic_index["GOKEY"]="84"
mnemonic_index["GOSUB"]="82"
mnemonic_index["GOTO"]="80"
mnemonic_index["HIT"]="94"
mnemonic_index["IF"]="86"
mnemonic_index["INPUT"]="96"
mnemonic_index["KEY"]="8E"
mnemonic_index["LET"]="90"
mnemonic_index["LIST"]="9E"
mnemonic_index["LOAD"]="A0"
mnemonic_index["MEM"]="80"
mnemonic_index["NEW"]="92"
mnemonic_index["PRINT"]="88"
mnemonic_index["REM"]="8C"
mnemonic_index["RETURN"]="8E"
mnemonic_index["RND"]="98"
mnemonic_index["RUN"]="8A"
mnemonic_index["SAVE"]="98"
mnemonic_index["SHOW"]="9A"
#mnemonic_index["THEN"]="80"
mnemonic_index["TI"]="8A"
mnemonic_index["TVOFF"]="A6"
mnemonic_index["TVON"]="A2"

# Return list of relevant text files from a directory
def GetFiles(directory,extensions):
    matched = []
    for ext in extensions:
        wild = os.path.join(directory, f'*{ext}')
        matched.extend(glob.glob(wild))
    return matched

# Create a single square wave cycle of a given frequency
def make_square_wave(freq,framerate):
    n = int(framerate/freq/2)
    return bytearray([CENTER-AMPLITUDE//2])*n + \
           bytearray([CENTER+AMPLITUDE//2])*n

# Create the wave patterns that encode 1s and 0s
one_pulse  = make_square_wave(ONES_FREQ,FRAMERATE)
zero_pulse = make_square_wave(ZERO_FREQ,FRAMERATE)

def is_even(number):
    return number % 2 == 0

def Extract_Number_String(text):
    
    text=text.upper()
    match = re.match(r"^(\d+)(.*)", text)
    if match:
        number_str, remaining_str = match.groups()
        return int(number_str), remaining_str.lstrip()
    else:
        return None, text


# Return byte length in hex from hex string as "A0 00 53 00 00 00 00 00" or with no spaces
def get_basic_size(hex_string,asHex=1,offset=0,pad=2):
    # Remove spaces if present
    hex_string = hex_string.replace(" ", "")
    byte_object = bytes.fromhex(hex_string)
    basic_size = len(byte_object) + offset
    if asHex:
        basic_size=integer_to_hex(basic_size,pad)
    return basic_size
def hex_to_binary(hex_array,pad=8):
    
    binary_array = []

    for hex_digit in hex_array:
        integer_value = int(hex_digit, 16)
        binary_string = bin(integer_value)[2:].zfill(pad)
        binary_array.append(binary_string)
    return binary_array

def string_to_binary(input_string,pad=8):
    binary_representation = []
    for char in input_string:
        # Get the ASCII value of the character
        ascii_value = ord(char)
        # Convert the ASCII value to an 8-bit binary string (e.g., '01001000')
        binary_char = format(ascii_value, '08b')
        binary_representation.append(binary_char)
    return ' '.join(binary_representation).zfill(pad)

def string_to_hex(var):
   return integer_to_hex(ord(var))

def integer_to_hex(var,pad=2):
    return hex(var)[2:].upper().zfill(pad)
   
def Create_BinData(SourceFile):        
    with open(SourceFile, 'r', encoding='utf-8') as file:
        text_content = file.read()
        text_segment = text_content.split('\n')   # Line and Code
        indexed_data = {i: seg for i, seg in enumerate(text_segment)} 
    
    if (DEBUG):
        print("Text Array")
        print(indexed_data)
    
    
    # Initialize arrays
    code_array=[]
    code_segment_hex=[]
    final_hex_array = []
    temp_array = []
    
    # Split line into label and code
    for i in range(len(indexed_data)):
        label,code=Extract_Number_String(indexed_data[i])
        if label==None or label=='':
            continue
      
        hex_string = integer_to_hex(label,4)
        label_hex1 = hex_string[:2]
        label_hex2 = hex_string[2:]
         
        code_segment = re.split(r'(\s+)', code)
        code_segment.extend('\r')
        
        code_segment_hex=[]
        temp_array=[] 
        nospc=0
                    
        for index,word in enumerate(code_segment):
            # swizzle value if we have a tabled mnemonic defined
            if word in mnemonic_index:
                if index==0:
                    nospc=1
                code_segment_hex.append(mnemonic_index[word])
                continue
            
            for letter in word:
                # ignore first space after a mapped mnemonic
                if index==1 and ord(letter)==32 and nospc:
                    nospc=0
                    continue
                code_segment_hex.append(string_to_hex(str(letter)))
            hex_string=' '.join(code_segment_hex)
            basic_line_hex = get_basic_size(hex_string,1,1)
        
        temp_array.append(label_hex1)
        temp_array.append(label_hex2)
        temp_array.append(basic_line_hex)
        temp_array.extend(code_segment_hex)
        code_array.extend(temp_array)
    if (DEBUG):
        print("Code Array")
        print(code_array)   
    hex_string=' '.join(code_array)
    basic_size_hex=get_basic_size(hex_string,1,10,4)
    basic_size_hex1 = basic_size_hex[:2]
    basic_size_hex2 = basic_size_hex[2:]
    
    final_hex_array = []
    final_hex_array.append(basic_size_hex1)
    final_hex_array.append(basic_size_hex2)
    
    #zero byte repeated 6 times
    for i in range(6):
        final_hex_array.append(integer_to_hex(0))    
         
    final_hex_array.extend(code_array)
 
    total_sum = 0
    for hex_num_str in final_hex_array:
        total_sum += int(hex_num_str, 16)
    
    total_hex = integer_to_hex(total_sum,4)
    total_hex1 = total_hex[:2]
    total_hex2 = total_hex[2:]
    
    final_hex_array.insert(0, total_hex2)
    final_hex_array.insert(0, total_hex1)
    binary_array=hex_to_binary(final_hex_array,8)
    if (DEBUG):
        print("Binary Array")
        print(binary_array)
    return binary_array
   
# Take a single byte value and turn it into a bytearray representing
# the associated waveform along with the required start and stop bits.
def Encode_Data(bytes):
    # Reverse binary sequence to little endian 
    bytes= bytes[::-1]
    # The start bit (0 or 1)
    if (STARTBIT==0):
        encoded = bytearray(zero_pulse)
    else:
        encoded = bytearray(one_pulse)
    p = 0
    # 8 data bits
    for bit in bytes:
        if (int(bit)==1):
            encoded.extend(one_pulse)
            p=p+1
        else:
            encoded.extend(zero_pulse)
              
    # add parity
    if is_even(p)==0:
        encoded.extend(one_pulse)        
    else:
        encoded.extend(zero_pulse)
    
    return encoded

# Write Tag
def Write_Tag(filename,text1):
    with taglib.File(filename) as file:
        file.tags["ARTIST"] = [text1]    
        file.tags["ALBUM"] = [text1]
        file.tags["TITLE"] = [text1]
        file.save()

# Write a WAV file with encoded data. leader and trailer specify the
# number of seconds of carrier signal to encode before and after the data
def Write_Wav(TargetFile,Binary_Data):
    w = wave.open(TargetFile,"wb")
    w.setnchannels(1)
    w.setsampwidth(1)
    w.setframerate(FRAMERATE)

    # Write the leader
    w.writeframes(zero_pulse*(int(FRAMERATE/len(zero_pulse))*LEADER))
    
    # Encode the actual data
    for byte in Binary_Data:
        w.writeframes(Encode_Data(byte))
    
    # Write terminating blank with single Bit 1    
    for x in range(BLANKS):
        w.writeframes(one_pulse)
                
    w.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) != 1:
        print("Usage : %s" % sys.argv[0],file=sys.stderr)
        raise SystemExit(1)

    import click,os,glob,re,taglib,wave
    from colorama import Fore, Back, Style, init
    from pathlib import Path
       
    os.system('cls')
    init(autoreset=True)
    print(f'{Fore.RED}{Style.BRIGHT}Basic Text To Wav File Conversion\n')
    print(f'{Fore.GREEN}{Style.BRIGHT}File Settings')
    # Prompts
    SourceDir = click.prompt(f'{Fore.BLUE}{Style.BRIGHT}Basic Text Source Directory', type=click.Path(exists=True), default=os.getcwd(),hide_input=False,show_choices=False,show_default=False,prompt_suffix=' <'+os.getcwd()+'> : ')
    if not SourceDir.endswith(os.sep):
        SourceDir = SourceDir + os.sep

    TargetDir = click.prompt(f'{Fore.BLUE}Target Directory', type=click.Path(exists=False), default=os.getcwd(),hide_input=False,show_choices=False,show_default=False,prompt_suffix=' <'+os.getcwd()+'> : ')
    if not TargetDir.endswith(os.sep):
        TargetDir = TargetDir + os.sep
        
    print(f'{Fore.GREEN}{Style.BRIGHT}\nWav File Parameters')
    
    ZERO_FREQ = int(click.prompt(f'{Fore.YELLOW}Bit 0 Frequency Hz' ,default=str(ZERO_FREQ), type=click.Choice(['300','500','600','800','1000','1200','2000','2400','4800','9600']),hide_input=False,show_choices=False,show_default=False,prompt_suffix=' <'+str(ZERO_FREQ)+'> :'))   
    ONES_FREQ = int(click.prompt(f'{Fore.YELLOW}Bit 1 Frequency Hz' ,default=str(ONES_FREQ), type=click.Choice(['300','500','600','800','1000','1200','2000','2400','4800','9600']),hide_input=False,show_choices=False,show_default=False,prompt_suffix=' <'+str(ONES_FREQ)+'> :'))
    FRAMERATE = int(click.prompt(f'{Fore.YELLOW}Framerate Hz' ,default=str(FRAMERATE), type=click.Choice(['4800','9600','11025','22050','44100','48000']),hide_input=False,show_choices=False,show_default=False,prompt_suffix=' <'+str(FRAMERATE)+'> :'))
    AMPLITUDE = int(click.prompt(f'{Fore.YELLOW}Amplitude' ,default=str(AMPLITUDE), type=click.IntRange(0, 255),hide_input=False,show_default=False,prompt_suffix=' <'+str(AMPLITUDE)+'> :'))
    LEADER    = int(click.prompt(f'{Fore.YELLOW}Leader in seconds' ,default=str(LEADER),type=click.IntRange(0, 60),hide_input=False,show_default=False,prompt_suffix=' <'+str(LEADER)+'> :'))
    STARTBIT  = int(click.prompt(f'{Fore.YELLOW}Start Bit 0 or 1',default=str(STARTBIT),type=click.IntRange(0, 1),hide_input=False,show_default=False,prompt_suffix=' <'+str(STARTBIT)+'> :'))
    BLANKS    = int(click.prompt(f'{Fore.YELLOW}Terminating bit 1 sequence',default=str(BLANKS),type=click.IntRange(0, 300),hide_input=False,show_default=False,prompt_suffix=' <'+str(BLANKS)+'> :'))     
    
    DEBUG     = click.confirm(f'{Fore.BLUE}{Style.BRIGHT}\nShow debug data ?',default='n')
 
    AlphaDir  = click.confirm(f'{Fore.MAGENTA}\nDo you want to save files in alphabetized directories ?',default='Y')
    Extension = ['.bas','.txt','.text']
    Files_Found = GetFiles(SourceDir,Extension)
    if Files_Found:
        print(f'{Fore.GREEN}\nFiles to be converted :')
        for fileStr in Files_Found:
            print(os.path.basename(fileStr))
    else:
        click.pause(f'{Fore.RED}{Style.BRIGHT}\nNo Files Found. Press any key to exit')
        sys.exit()
              
    if click.confirm(f'{Fore.RED}{Back.BLACK}\nProceed ?',default='Y'):
        for SourceFile in Files_Found:    
            FileName=os.path.splitext(os.path.basename(SourceFile))[0]
            AlphaName=FileName[0].upper()
            WavDir = os.path.join(TargetDir, 'wav')
        
            if not os.path.exists(WavDir):
                os.makedirs(WavDir)
            
            if (AlphaDir):
                WavDir=os.path.join(WavDir,AlphaName)
                if not os.path.exists(WavDir):
                        os.makedirs(WavDir)    
            
            TargetFile=os.path.join(WavDir, FileName +'.wav')         
            Binary_Data=Create_BinData(SourceFile)
            FName=Path(TargetFile).resolve().stem
            
            print(f'{Fore.YELLOW}Creating File {TargetFile}')
            Write_Wav(TargetFile,Binary_Data)
            Write_Tag(TargetFile,FName)
    else:
        click.pause(f'{Fore.RED}{Style.BRIGHT}\nABORTED. Press the any key to exit')
        sys.exit()