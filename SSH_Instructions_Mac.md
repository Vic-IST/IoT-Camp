# SSH into Your Raspberry Pi (Mac)

1. Open **Terminal** — press `Cmd + Space`, type **Terminal**, press Enter
2. Type this and press Enter:
   ```
   ssh ai@<Pi IP address>
   ```
   Replace `<Pi IP address>` with the address written on the board.
3. If it asks *"Are you sure you want to continue connecting?"* — type `yes` and press Enter
4. Type the password when prompted *(nothing will appear as you type — that's normal)*
5. You're in when you see:
   ```
   ai@cookie:~ $
   ```

**To disconnect:** type `exit` and press Enter

---

## Install Flask and paho-mqtt (do once on Tuesday)

```
pip install flask paho-mqtt --break-system-packages
```
