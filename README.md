# WiFiCom Update Tool

Use this tool to install your initial WiFiCom files or to update an existing WiFiCom to a newer release.  Also works for downgrading!

## Mac read first!
- Please ensure MacOS is updated to 15.2 or higher.
- On MacOS 14.4 to 15.1, updates are slow, may cause excessive flash wear on your WiFiCom, and may have issues upgrading CircuitPython.
- MacOS 14.0 to 14.3 will corrupt files on CIRCUITPY drives.

## Updating (WiFiCom)
- Back up the files on your CIRCUITPY drive if you changed anything important. This tool aims to preserve previous WiFiCom config and only delete/overwrite specific files, but be cautious about any files you don't want to lose.
- Put the WiFiCom into Drive Mode using the menu.
- Run the update tool and select an option.
- If a CircuitPython upgrade/downgrade is recommended, the tool will link to the appropriate file.
  - Choose "Download UF2 file" to save the file using your web browser.
  - Eject (safely remove) the CIRCUITPY drive from your computer.
  - Exit Drive Mode by holding the C button.
  - Put the unit into bootloader mode using the option in the Settings menu.
  - Copy the UF2 file into the RPI-RP2 drive that appears.
  - When the WiFiCom has rebooted, put it back into drive mode, and re-run the update tool with the same option as before.
- Wait for the update to complete.
- Eject (safely remove) the CIRCUITPY drive from your computer.
- Exit Drive Mode by holding the C button.

## Updating (P-Com)
- Back up the files on your CIRCUITPY drive if you changed anything important. This tool aims to preserve previous WiFiCom config and only delete/overwrite specific files, but be cautious about any files you don't want to lose.
- Put the P-Com into Dev Mode: disconnect the USB, reconnect while holding the main button, and keep holding until the CIRCUITPY drive appears.
- Run the update tool and select an option.
- If a CircuitPython upgrade/downgrade is recommended, the tool will link to the appropriate file.
  - Choose "Download UF2 file" to save the file using your web browser.
  - Eject (safely remove) the CIRCUITPY drive from your computer.
  - Put the unit into bootloader mode using the instructions for your board below.
  - Copy the UF2 file into the RPI-RP2 drive that appears. While copying, hold the main button until the CIRCUITPY drive reappears.
  - Re-run the update tool with the same option as before.
- Wait for the update to complete.
- Eject (safely remove) the CIRCUITPY drive from your computer.
- Disconnect and reconnect the USB to reboot the device.

## Installing on a new build
- Install the appropriate version of CircuitPython (see [wificom-lib](https://github.com/mechawrench/wificom-lib)). On a fresh board, the RPI-RP2 drive appears by default. Otherwise, enter bootloader mode using the instructions below.
- If you are using a custom circuit layout, modify "board_config.py" from wificom-lib and save it to your CIRCUITPY drive.
- Run the update tool and select an option.
- Wait for the installation to complete.
- If you wish to use WiFi, create a new WiFiCom on https://wificom.dev/ and follow the "Credentials Download" instructions on the page that appears.
- Eject (safely remove) the CIRCUITPY drive from your computer.
- Disconnect and reconnect the USB / power supply.

## Exceptions (other boards, older versions, non-bootable)
### Making the CIRCUITPY drive writeable
- WiFiCom (2.x) Dev Mode: connect the unit to USB while holding the C button, and keep holding until the CIRCUITPY drive appears.
- WiFiCom (1.x) Dev Mode: connect the unit to USB while holding the C button, then release the button promptly when the LED comes on.
### Rebooting into normal mode (make CIRCUITPY read-only again)
- **First** eject (safely remove) the CIRCUITPY drive from your computer.
- Older WiFiCom firmware in "Drive Mode": select a different mode from the menu.
- Screenless units / WiFiCom in "Dev Mode" / not running: disconnect and reconnect the USB / power supply.
- Arduino Nano RP2040 Connect: press the RESET button once.
### Bootloader mode
- Most boards: disconnect the USB / power supply, reconnect while holding the BOOT button, and keep holding until the RPI-RP2 drive appears.
- Xanthos's premade units: the BOOT button is on the back. On battery units you will need to detach the battery module. You may need a tool to press the button.
- Arduino Nano RP2040 Connect: double-click the RESET button.
