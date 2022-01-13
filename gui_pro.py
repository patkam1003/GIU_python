import PySimpleGUI as sg
import re
import serial
from terminal import *
import time
import threading

THREAD_EVENT = '-THREAD-'



def the_thread(window):
    """
    The thread that communicates with the application through the window's events.

    Once a second wakes and sends a new event and associated value to the window
    """
    i = 0
    while True:
        time.sleep(1)
        window.write_event_value('-THREAD-', (threading.current_thread().name, i))      # Data sent is a tuple of thread name and counter
        i += 1


sg.theme('DarkAmber')   # Add a touch of color
# All the stuff inside your window.
col1 = [
        #[sg.Button('otworz plik' , key="-open_file_key1-"),sg.InputText(key="-in_hex_path-")],
        [sg.In(key="-open_file_key-",enable_events=True),sg.FileBrowse(file_types=(("Text Files","*.hex"),))],
        [sg.Text('Rozmiar pliku'), sg.Text(key="-in_file_size-")],
        [sg.Multiline(key="-in_file_text-", size = (50, 10))]

        ]


col2 = [
        [sg.Text('Port'),sg.InputCombo(values=ask_for_port(), size=(10, 1),key="-combo_port-",enable_events = True), sg.Text('Baud'),sg.InputCombo(('9600', '19200', '38400','115200'), size=(10, 1),key="-combo_baud-", default_value = '9600')],
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

def read_info(window, values):
    print(values['-combo_port-'])
    if values['-combo_port-'] == "":
        window['-out_info-'].update("Wybierz port COM")
        return
    try:
        serial_instance = serial.serial_for_url(
            values['-combo_port-'],
            int(values['-combo_baud-']),
            parity="N",
            rtscts=False,
            xonxoff=False,
            do_not_open=True,
            timeout = 10    #timeout read 10s
            )
        print("debug1")

        if isinstance(serial_instance, serial.Serial):
            serial_instance.exclusive = True #args.exclusive    #disable looking for native ports
        print("debug2")

        serial_instance.open()
        print("debug3")
    except serial.SerialException as e:
        sys.stderr.write('could not open port {!r}: {}\n'.format(values['-combo_port-'], e))
        window['-out_info-'].update("Nie mozna otworzyc portu COM")

    #oczekiwanie na znak zapytania z procesora 

    if values['-checkbox_RST-'] == True:
        serial_instance.write(b'AT+RST?\r\n')
        serial_instance.reset_input_buffer()


    timeout_start_time = int(round(time.time()))
    while True:   
        data = serial_instance.read(serial_instance.in_waiting or 1)
        print(data, type(data))
        input_raw_data = ""
        if data:
            input_raw_data =  input_raw_data + data.decode("utf-8")
            try:
                data_table = re.search(r'.*\?.*', input_raw_data)
                if data_table != None:
                    data_ack = 1
                    print(data_ack)
                    
            except:
                print("dupa")

            if data_ack == 1:
                try:
                    #serial_instance.write(b'AT+RST?\r\n')
                    #time.sleep(0.1)
                    serial_instance.write(b'u')
                    time.sleep(0.1)
                    serial_instance.write(b'i')
                    break
                except:
                    window['-out_info-'].update("Problem z połączeniem")
                    serial_instance.close()
                    return
        if (int(round(time.time())) - timeout_start_time) > 10:
            window['-out_info-'].update("Brak danych BLS")
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
            print(data, type(data))
            if data:
                input_raw_data =  input_raw_data + data.decode("utf-8") #str(data)
                print(input_raw_data)
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
                        window['-out_info-'].update(info_output)
                        serial_instance.close()
                        cpu_flash_size = int(data_table.group(2), 16)
                        page_size = int(data_table.group(1))
                        break
                except:
                    window['-out_info-'].update("Niepoprawne dane BLS")
                    serial_instance.close()
                    break 

                #sprawdzam timeout 
                if (int(round(time.time())) - timeout_start_time) > 10:
                        window['-out_info-'].update("Brak danych BLS")
                        serial_instance.close()
                        break

            elif data == b'':
                #timeout#3
                window['-out_info-'].update("Timeout!")
                serial_instance.close()
                break
        
    except:
        print("dupa blada")
    serial_instance.close()




def upload_program(window, values):
    global flash_file_content
    global page_size
    global cpu_flash_size
    file_size = len(flash_file_content)
    data_sent_cnt = 0

    if not flash_file_content:
        window['-out_info-'].update("Wybierz plik flash")
        return

    print(file_size/2,cpu_flash_size)
    if file_size/2 > cpu_flash_size:

        window['-out_info-'].update("Procesor jest za maly")
        return

    if (page_size != 0) and (cpu_flash_size != 0):
        try:
            serial_instance = serial.serial_for_url(
                values['-combo_port-'],
                int(values['-combo_baud-']),
                parity="N",
                rtscts=False,
                xonxoff=False,
                do_not_open=True,
                timeout = 10    #timeout read 10s
                )
            print("debug1")

            if isinstance(serial_instance, serial.Serial):
                serial_instance.exclusive = True #args.exclusive    #disable looking for native ports
            print("debug2")

            serial_instance.open()
            print("debug3")
        except serial.SerialException as e:
            sys.stderr.write('could not open port {!r}: {}\n'.format(values['-combo_port-'], e))
            window['-out_info-'].update("Nie mozna otworzyc portu COM")

        #Ładowanie Programu

        try:
            serial_instance.write(b'w')
            status = 0
            data_ack = 0
            timeout_start_time = int(round(time.time()))

            while True:
                data = serial_instance.read(serial_instance.in_waiting or 1)
                print(data, type(data))
                input_raw_data = ""
                if data:
                    input_raw_data =  input_raw_data + data.decode("utf-8") #str(data)
                    print(input_raw_data)
                    try:
                        data_table = re.search(r'.*@.*', input_raw_data)
                        if data_table != None:
                            data_ack = 1
                            print(data_ack)
                            timeout_start_time = int(round(time.time()))
                    except:
                        print("dupa")

                    if data_ack == 1:
                        data_ack = 0
                        input_raw_data = ""
                        page = '01'

                        for cnt in range(page_size*2):
                            page = page + flash_file_content[(cnt +data_sent_cnt)% file_size]

                        print("Page ," ,page)
                        serial_instance.write(bytearray.fromhex(page))
                        print("wyslano")

                        data_sent_cnt += page_size*2
                        if data_sent_cnt >= file_size:
                            # print("out", serial_instance.out_waiting)
                            # while serial_instance.out_waiting >0:
                            #     print("teeeest")
                            #     pass
                            time.sleep(2)
                            window['-out_info-'].update("DONE")
                            serial_instance.close()
                            return

                        
                        print("data_sent_cnt", data_sent_cnt)


 
                    #sprawdzam timeout 
                    if (int(round(time.time())) - timeout_start_time) > 10:
                        window['-out_info-'].update("Brak danych BLS")
                        serial_instance.close()
                        break
                elif data == b'':
                    #timeout#3
                    window['-out_info-'].update("Timeout!")
                    serial_instance.close()
                    break

        except:
            print("dupa2")







    else:
        return



   


def main():
    # Create the Window
    window = sg.Window('Window Title', layout)
    global flash_file_content
    global page_size
    global cpu_flash_size
    flash_file_content = ""
    com_port_uchwyt = None
    miniterminal = None
    # Event Loop to process "events" and get the "values" of the inputs
    while True:
        event, values = window.read()
        print(event)
        if event == sg.WIN_CLOSED: # if user closes window or clicks cancel
            break

        elif event == "-open_file_key-":
            try:
                reader = open(values["-open_file_key-"],"r")
                contents =reader.readlines()
                flash_file_content = ""
                for line in contents:
                    flash_file_content = flash_file_content+re.search(r':.{8}(.*)..', line).group(1)

                window['-in_file_text-'].update(flash_file_content)
                window['-in_file_size-'].update(str(len(flash_file_content)//2)+" kB")
                print(len(flash_file_content))
                reader.close()
            except:
                print("test")
            

        elif event == "-combo_port-":
            print("dupa")

        elif event == "-info_key-":
            read_info(window, values)
            #print(cpu_flash_size, page_size)
        elif event == "-upload_key-":
            read_info(window, values)
            upload_program(window, values)

        if event == THREAD_EVENT:
            pass


    window.close()


if __name__ == '__main__':
    main()