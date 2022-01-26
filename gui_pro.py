import PySimpleGUI as sg
import re
import serial
from terminal import *
import os, time, datetime
import threading
import pathlib
from sys import platform
import sys
import getopt 




#THREAD_EVENT = '-THREAD-'
#OPEN_FILE_KEY = '-open_file_key-'




sg.theme('DarkAmber')   # Add a touch of color
# All the stuff inside your window.
col1 = [
        #[sg.Button('otworz plik' , key="-open_file_key1-"),sg.InputText(key="-in_hex_path-")],
        [sg.In(key="-open_file_key-",enable_events=True),sg.FileBrowse(file_types=(("Text Files","*.hex"),))],
        [sg.Text('Rozmiar pliku'), sg.Text(key="-in_file_size-")],
        [sg.Multiline(key="-in_file_text-", size = (50, 10))]

        ]


col2 = [
        [sg.Text('Port'), sg.InputCombo(values=ask_for_port(), size=(10, 1), key="-combo_port-",enable_events = True), sg.Text('Baud'),sg.InputCombo(('9600', '19200', '38400','115200'), size=(10, 1),key="-combo_baud-", default_value = '9600')],
        [sg.Text('COM: ', key="-COM_name-")],
        [sg.Checkbox('AT+RST?', size=(10,1),key="-checkbox_RST-"),  sg.Checkbox('Test')],
        [sg.Frame(layout=[
            [sg.Button('Info' , key="-info_key-"),sg.Button('Upload' , key="-upload_key-")],
            [sg.Multiline(key="-out_info-", size = (40, 10))]
    ], title='Bootloader',title_color='green', relief=sg.RELIEF_SUNKEN)]

]


layout = [
            [
            sg.Column(col1),
            sg.VSeparator(),
            sg.Column(col2)
            ]
] 

flash_file_content = ""
info_output = ""
cpu_flash_size = 0
page_size = 0
flag = 0
thread_lock = False
serial_instance = None


def load_file(filename):
    reader = open(filename, "r")
    contents = reader.readlines()
    flash_file_content = ""
    for line in contents:
        flash_file_content = flash_file_content + re.search(r':.{8}(.*)..', line).group(1)

    print("[load_file]długość pliku ", len(flash_file_content))
    return flash_file_content

def load_file_window(window, values):
    global flag
    global flash_file_content
    try:
        window['-in_file_text-'].update('')
        filename = values["-open_file_key-"]
        flash_file_content = load_file(filename)
        print("[load_file_window] załadowano plik")
        # reader = open(filename, "r")
        # contents = reader.readlines()
        # flash_file_content = ""
        # for line in contents:
        #     flash_file_content = flash_file_content + re.search(r':.{8}(.*)..', line).group(1)

        window['-in_file_text-'].update(flash_file_content)
        window['-in_file_size-'].update(str(len(flash_file_content) // 2) + " kB")
        print("[load_file_window]długość pliku ", str(len(flash_file_content)))
        reader.close()
        flag = 0
    except:
        print("[load_file_window]LOG: nie wybrano pliku")





def the_thread(window, values):
    fname = pathlib.Path(values["-open_file_key-"])
    global flag
    date_start = datetime.datetime.fromtimestamp(fname.stat().st_mtime)
    while True:
        time.sleep(1)

        if platform == "linux" or platform == "linux2":
            if date_start != (datetime.datetime.fromtimestamp(fname.stat().st_mtime)):
                flag = 1
                date_start = datetime.datetime.fromtimestamp(fname.stat().st_mtime)

        elif platform == "win32":
            if date_start != (datetime.datetime.fromtimestamp(fname.stat().st_mtime)):
                flag = 1
                date_start = datetime.datetime.fromtimestamp(fname.stat().st_mtime)

        if flag == 1:
            load_file(window, values)

# def the_thread_upload(window, values):

def read_info(com, baud, rst, window = None, values = None):
    global serial_instance
    #print(values['-combo_port-'])
    # if values['-combo_port-'] == "":
    #     window['-out_info-'].update("Wybierz port COM")
    #     return
    try:
        serial_instance = serial.serial_for_url(
            com,
            int(baud),
            parity="N",
            rtscts=False,
            xonxoff=False,
            do_not_open=True,
            timeout = 10    #timeout read 10s
            )
        print("[read_info]","debug1")

        if isinstance(serial_instance, serial.Serial):
            serial_instance.exclusive = True #args.exclusive    #disable looking for native ports
        print("[read_info]","debug2")

        serial_instance.open()
        print("[read_info]","debug3")
    except serial.SerialException as e:
        sys.stderr.write('could not open port {!r}: {}\n'.format(com, e))
        if window:
            window['-out_info-'].update("Nie mozna otworzyc portu COM")

    #oczekiwanie na znak zapytania z procesora 

    if rst:
        serial_instance.write(b'AT+RST?\r\n')
        serial_instance.reset_input_buffer()

    data_ack = 0
    timeout_start_time = int(round(time.time()))
    while True:   
        data = serial_instance.read(serial_instance.in_waiting or 1)
        print("[read_info] data: ",data, type(data))
        input_raw_data = ""
        if data:
            try:
                input_raw_data =  input_raw_data + data.decode("utf-8",errors='ignore')
                data_table = re.search(r'.*\?.*', input_raw_data)
                if data_table:
                    data_ack = 1
                    print("[read_info] odebrano znak zapytania")
                    
            except:
                print("[read_info]"," Znak zapytania nie odebrany")

            if data_ack == 1:
                try:
                    #serial_instance.write(b'AT+RST?\r\n')
                    #time.sleep(0.1)
                    serial_instance.write(b'u')
                    time.sleep(0.1)
                    serial_instance.write(b'i')
                    print("[read_info] Wysyłam  u i i ")
                    break
                except:
                    if window:
                        window['-out_info-'].update("Problem z połączeniem")

                    print("[read_info]"," Problem z połączeniem, zamkniecie portu")
                    serial_instance.close()
                    return
        if (int(round(time.time())) - timeout_start_time) > 10:
            if window:
                window['-out_info-'].update("Timeout, Brak danych BLS")
            print("[read_info]"," Timeout, Brak danych BLS, zamkniecie potru")
            serial_instance.close()
            break

    input_raw_data = ""
    output_tekst= ""
    timeout_start_time = int(round(time.time()))
    try:
        #time_start = time.read()
       # print(time_start)
        while True:
        # read all that is there or wait for one byte
            data = serial_instance.read(serial_instance.in_waiting or 1)
            print("[read_info] data: ", data, type(data))
            if data:
                input_raw_data =  input_raw_data + data.decode("utf-8",errors='ignore') #str(data)
                print("[read_info] odebrano: ",input_raw_data)
                try:
                    data_table = re.search(r'\?*&(\d+),0x([0-9a-fA-F]+),([0-9a-zA-Z]+),(\d+),(\d+)\*', input_raw_data)
                    #parsuj regexa
                    if data_table != None:
                        global info_output
                        global cpu_flash_size
                        global page_size
                        info_output = "Page size: " + str(data_table.group(1)) + "\n"
                        info_output = info_output + "Flash size: " + str(data_table.group(2)) + "\n"
                        info_output = info_output + "CPU name: " + str(data_table.group(3)) + "\n"
                        info_output = info_output + "CPU frequency: " + str(data_table.group(4)) + "\n"
                        info_output = info_output + "BLS Version: " + str(data_table.group(5)) + "\n"
                        if window:
                            window['-out_info-'].update(info_output)

                        #serial_instance.close()
                        cpu_flash_size = int(data_table.group(2), 16)
                        page_size = int(data_table.group(1))
                        return info_output
                except:
                    if window:
                        window['-out_info-'].update("Niepoprawne dane BLS")
                    print("[read_info] Niepoprawne dane BLS ")
                    serial_instance.close()
                    break 

                #sprawdzam timeout 
                if (int(round(time.time())) - timeout_start_time) > 10:
                        if window:
                            window['-out_info-'].update("Brak danych BLS")
                        print("[read_info] Brak danych BLS ")
                        serial_instance.close()
                        break

            elif data == b'':
                #timeout#3
                if window:
                    window['-out_info-'].update("Timeout!")
                print("[read_info]","Timeout puste wiedomości")
                serial_instance.close()
                break
        
    except:
        print("[read_info]","Czytanie info nie zadziałało")
    # serial_instance.close()


def read_info_window(window, values):
    #print(values['-combo_port-'])
    if values['-combo_port-'] == "":
        window['-out_info-'].update("Wybierz port COM")
        return

    rst = values['-checkbox_RST-']
    com = values['-combo_port-']
    baud = values['-combo_baud-']
    info_output = read_info(com, baud, rst, window, values)



def upload_program(com, baud, window = None, values = None):
    print("[upload_program]start ")
    global flash_file_content
    global page_size
    global cpu_flash_size
    global serial_instance
    file_size = len(flash_file_content)
    data_sent_cnt = 0

    if not flash_file_content:
        print("[upload_program] Brak pliku ")
        if window:
            window['-out_info-'].update("Wybierz plik flash")
        return

    print(file_size/2,cpu_flash_size)
    if file_size/2 > cpu_flash_size:
        print("[upload_program] Procesor jest za mały ")
        if window:
            window['-out_info-'].update("Procesor jest za maly")
        return

    if (page_size != 0) and (cpu_flash_size != 0):
        # try:
        #     serial_instance = serial.serial_for_url(
        #         com,
        #         int(baud),
        #         parity="N",
        #         rtscts=False,
        #         xonxoff=False,
        #         do_not_open=True,
        #         timeout = 10    #timeout read 10s
        #         )
        #     print("[upload_program]","Parametry serial ok")

        #     if isinstance(serial_instance, serial.Serial):
        #         serial_instance.exclusive = True #args.exclusive    #disable looking for native ports
        #         print("[upload_program]","debug2")

        #     serial_instance.open()
        #     print("[upload_program]","otwarcie portu ok")
        # except serial.SerialException as e:
        #     sys.stderr.write('could not open port {!r}: {}\n'.format(com, e))
        #     print("[upload_program] Nie można otworzyć portu ")
        #     if window:
        #         window['-out_info-'].update("Nie mozna otworzyc portu COM")

        #Ładowanie Programu
        print("[upload_program] start, ", serial_instance)
        try:
            serial_instance.write(b'w')
            status = 0
            data_ack = 0
            timeout_start_time = int(round(time.time()))

            while True:
                data = serial_instance.read(serial_instance.in_waiting or 1)
                print("[upload_program] data: ", data, type(data))
                input_raw_data = ""
                if data:
                    input_raw_data = input_raw_data + data.decode("utf-8",errors='ignore') # str(data)
                    print("[upload_program] odebrano: ", input_raw_data)
                    try:
                        data_table = re.search(r'(.*@.*)|(.*\?.*)', input_raw_data)
                        if data_table.group(1) != None:
                            data_ack = 1
                            print("[upload_program] odebrano małpę ",data_ack)
                            timeout_start_time = int(round(time.time()))
                            #zakonczenie ladowania
                            if data_sent_cnt >= file_size:
                                # print("out", serial_instance.out_waiting)
                                # while serial_instance.out_waiting >0:
                                #     print("teeeest")
                                #     pass
                                #time.sleep(2)
                                print("[upload_program]  DONE")
                                if window:
                                    window['-out_info-'].print("\r\nDONE")
                                serial_instance.close()
                                return
                        elif data_table.group(2) != None:
                            serial_instance.write(b'w')
                    except:
                        print("[upload_program]","Nie wysłano programu, procesor nie wysyła @")

                    if data_ack == 1:
                        data_ack = 0
                        input_raw_data = ""
                        page = '01'

                        for cnt in range(page_size*2):
                            page = page + flash_file_content[(cnt +data_sent_cnt)% file_size]

                        print("[upload_program]","Page ," ,page)
                        serial_instance.write(bytearray.fromhex(page))
                        print("[upload_program]","wyslano")
                        if window:
                            window['-out_info-'].print(".", end='')

                        data_sent_cnt += page_size*2

                        print("[upload_program]","data_sent_cnt:", data_sent_cnt)


 
                    #sprawdzam timeout 
                    if (int(round(time.time())) - timeout_start_time) > 10:
                        if window:
                            window['-out_info-'].update("[upload_program] Brak danych BLS")
                        serial_instance.close()
                        break
                elif data == b'':
                    #timeout#3
                    if window:
                        window['-out_info-'].update("Timeout!")

                    print("[upload_program]","Timeout, odbieranie pustych wiadomosci")
                    serial_instance.close()
                    break

        except:
            print("[upload_program]","ładowanie programu poszło nie tak")
        #koniec programu 
        serial_instance.close()

    else:
        return




def upload_program_window(window, values):
    rst = values['-checkbox_RST-']
    com = values['-combo_port-']
    baud = values['-combo_baud-']
    upload_program(com, baud,window, values)
    


def read_upload(window, values):
    global thread_lock
    read_info_window(window, values)
    upload_program_window(window, values)
    thread_lock = False

def read_threading(window, values):
    global thread_lock
    read_info_window(window, values)
    global serial_instance
    serial_instance.close()
    thread_lock = False
   


def main():
    print("[main] Start, version V1.0")
    global flash_file_content
    global page_size
    global cpu_flash_size
    global flag
    global thread_lock
    global serial_instance
    if len(sys.argv) > 1:

        #tryb konsolowy
        print("[main] Tryb konsolowy")
        # print('ARGV      :', sys.argv[1:], len(sys.argv))

        baud = None
        com = None
        filename = None
        upload = False
        reset = False
        hhelp = False
        p = False
        d = False
        options, remainder = getopt.getopt(sys.argv[1:], 'uf:b:c:rpdh', ['update','file=','baudrate=','com=','reset','port','debug','help',])

        for opt, arg in options:
            if opt in ('-u', '--update'):
                upload = True
            elif opt in ('-f', '--file'):
                filename = pathlib.Path(arg).resolve()
                print("filename: ",filename)
            elif opt in ('-b', '--baudrate'):
                try:
                    baud = int(arg)
                except:
                    print("Invalid parameter type (-b)(expected number)")
                    return
                if arg == None: 
                    return -1
            elif opt in ('-c', '--com'):
                com = arg
                if arg == None: 
                    return -1             
            elif opt in ('-r', '--reset'):
                reset = True
            elif opt in ('-p', '--port'):
                p = True
            elif opt in ('-d', '--debug'):
                d = True
            elif opt in ('-h', '--help'):
                hhelp = True
        if p:
            for port in ask_for_port():
                print(port, ask_for_desc(port))    
            return
        if upload:
            # update

            #baud: sprawdzic czy wartosc jest tylko liczba
            if not baud:
                print("Baud is required")
                return

            #com sprawdzic czy com istnieje w systemie
            if com:
                if not (com in ask_for_port()):
                    for port in ask_for_port():
                        print(port, ask_for_desc(port)) 
                    print("COM port is required")   
                    return

            #file sprawdzic rozszerzenie i czy da sie otworzyc
            if filename:
                if not os.path.isfile(filename):
                    print("File not exists")
                    return
                if not (pathlib.Path(filename).suffix.lower() in ('.bin','.hex')):
                    print("File type incorrect (exp bin or hex)")
                    return

            flash_file_content =  load_file(filename)
            read_info(com, baud, reset)
            upload_program(com, baud)

        else:
            if not baud:
                print("Baud is required")
                return

            #com sprawdzic czy com istnieje w systemie
            if com:
                if not (com in ask_for_port()):
                    for port in ask_for_port():
                        print(port, ask_for_desc(port)) 
                    print("COM port is required")   
                    return
            read_info(com, baud, reset)
            serial_instance.close()


    else:

        #tryb graficzny
        # Create the Window
        window = sg.Window('Window Title', layout)

        flash_file_content = ""
        com_port_uchwyt = None
        miniterminal = None
        
        # Event Loop to process "events" and get the "values" of the inputs
        while True:
            event, values = window.read()
            print(event)
            if event == sg.WIN_CLOSED: # if user closes window or clicks cancel
                print("zamkniecie programu", event)
                break

            #elif event == '-open_file_key-':

            elif event == "-combo_port-":
                window['-COM_name-'].update("COM: " + ask_for_desc(values["-combo_port-"]))


            elif event == "-info_key-":
                # read_info(window, values)
                if thread_lock == False:
                    thread_lock = True
                    threading.Thread(target=read_threading, args=(window, values,), daemon=True).start()
                    print("[main] wciśnieto info, thread start")
                else:
                    print("[main] wciśnieto info, thread true - zablokowane")
                #print(cpu_flash_size, page_size)
            elif event == "-upload_key-":
                if thread_lock == False:
                    thread_lock = True
                    threading.Thread(target=read_upload, args=(window, values,), daemon=True).start()
                    print("[main] wciśnieto upload, thread start")
                else:
                    print("[main] wciśnieto upload, thread true - zablokowane")
                # upload_program(window, values)

            if event == '-open_file_key-':
                load_file_window(window, values)
                threading.Thread(target=the_thread, args=(window, values,), daemon=True).start()
                print("[main] wciśnieto open file, thread start")

        window.close()
        return 0


if __name__ == '__main__':
    main()