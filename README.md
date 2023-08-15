# WiFiCom Update Tool

Use this tool to install your initial WiFiCom files or to update an existing WiFiCom to a newer release.  Also works for downgrading!

## Updating
- Back up the files on your CIRCUITPY drive if you changed anything important. This tool aims to preserve previous WiFiCom config and only delete/overwrite specific files, but be cautious about any files you don't want to lose.
- Put your WiFiCom into Drive Mode using the menu.
  - If you cannot do this (because it is a screenless unit, or because something has gone wrong), then use Dev Mode instead: connect the WiFiCom to USB while holding the C button (the only button on screenless units) then release the button promptly when the LED comes on.
- Run the update tool and select an option.
- If a CircuitPython upgrade/downgrade is recommended, the tool will link to the appropriate file.
  - Choose "Download UF2 file" to save the file using your web browser.
  - Eject (safely remove) the CIRCUITPY drive from your computer.
  - On Pi Pico W, disconnect the USB / power supply, and reconnect while holding the BOOT button. On Nano RP2040 Connect, double-click the RESET button.
  - Copy the UF2 file into the RPI-RP2 drive that appears.
  - Re-run the update tool and select the same option as before.
- Wait for the update to complete.
- Eject (safely remove) the CIRCUITPY drive from your computer.
- If the WiFiCom is in "Drive Mode", select another option from the menu. If it is a screenless unit or in "Dev Mode", disconnect and reconnect the USB / power supply, or press the RESET button once if you have one.

## Installing on a new build
- Install the appropriate version of CircuitPython (see [wificom-lib](https://github.com/mechawrench/wificom-lib)) using the instructions above. On a fresh board, the RPI-RP2 drive appears by default.
- If you are using a custom circuit layout, modify "board_config.py" from wificom-lib and save it to your CIRCUITPY drive.
- Run the update tool and select an option.
- Wait for the installation to complete.
- Create a new WiFiCom on https://wificom.dev/ and follow the "Credentials Download" instructions on the page that appears.
- Eject (safely remove) the CIRCUITPY drive from your computer.
- Disconnect and reconnect the USB / power supply, or press the RESET button once if you have one.
