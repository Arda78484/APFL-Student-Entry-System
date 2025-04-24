# card_reader_controller.py
import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, QMetaObject, Qt
import time
import sys
import traceback

# --- Constants ---
ESP_BAUD_RATE = 9600          # Default baud rate, must match ESP32 code
READ_TIMEOUT = 1.0            # Serial readline timeout in seconds
LOOP_SLEEP = 0.05             # Short sleep in worker loop to yield thread
UID_PREFIX = "UID:"           # Prefix for Card UID messages from ESP32
ACK_PREFIX = "CMD:"           # Prefix for Acknowledgment messages from ESP32
CMD_SYSTEM_CHECK = "SYS_CHECK" # Command string to send for system check

# ==============================================================================
# Worker Class - Handles Serial I/O in Separate Thread
# ==============================================================================
class CardReaderWorker(QObject):
    """
    Worker object running in a separate thread for serial communication.
    Reads lines, parses messages based on defined prefixes (UID:, CMD:),
    and emits signals. Also handles sending commands to the device.
    """
    # --- Signals Emitted by Worker ---
    cardRead = pyqtSignal(str)          # Emitted with cleaned Card UID
    statusUpdate = pyqtSignal(str)      # Emitted for connection status changes
    errorOccurred = pyqtSignal(str)     # Emitted on serial or processing errors
    commandAckReceived = pyqtSignal(str)# Emitted with the acknowledged command (e.g., "CHECK_OK")

    def __init__(self, port, baud_rate=ESP_BAUD_RATE, parent=None):
        """
        Initializes the worker for a specific port and baud rate.
        """
        super().__init__(parent)
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None
        self._is_running = False # Controls the main loop execution
        print(f"DEBUG: Worker.__init__ - Port: {self.port}, Baud: {self.baud_rate}, Timeout: {READ_TIMEOUT}s")

    @pyqtSlot()
    def run(self):
        """
        Main execution method started by the thread. Connects to the serial
        port and enters the reading loop until stop() is called or an error occurs.
        """
        print(f"DEBUG: Worker.run - Starting execution for {self.port}...")
        self._is_running = True
        try:
            # --- 1. Connect to Serial Port ---
            print(f"DEBUG: Worker.run - Connecting to {self.port}...")
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=READ_TIMEOUT,
                write_timeout=READ_TIMEOUT
            )
            if not self.serial_connection.is_open:
                raise serial.SerialException(f"Port {self.port} failed to open.")

            self.statusUpdate.emit(f"✅ Bağlandı: {self.port}")
            print(f"DEBUG: Worker.run - Connection successful.")

            # --- 2. Reading Loop ---
            print("DEBUG: Worker.run - Entering read loop...")
            while self._is_running:
                # --- Check running flag before potential block ---
                if not self._is_running:
                    print("DEBUG: Worker.run - Loop check: Stop requested, breaking.")
                    break

                line_bytes = None
                try:
                    # --- Check connection status ---
                    if not self.serial_connection or not self.serial_connection.is_open:
                        if self._is_running: # Avoid error if already stopping
                            print("ERROR: Worker.run - Connection lost unexpectedly.")
                            self.errorOccurred.emit("❌ Seri bağlantı koptu.")
                        self._is_running = False
                        break # Exit loop

                    # --- Read line (blocks up to READ_TIMEOUT) ---
                    line_bytes = self.serial_connection.readline()

                    # --- Check running flag after potential block ---
                    if not self._is_running:
                        print("DEBUG: Worker.run - Loop check: Stop requested after read, breaking.")
                        break

                    # --- Process received data ---
                    if line_bytes:
                        self._process_line(line_bytes)

                # --- Handle Serial Errors during loop ---
                except serial.SerialException as e:
                    if self._is_running: # Report only if not stopping
                        print(f"ERROR: Worker.run - SerialException in loop: {e}")
                        traceback.print_exc()
                        self.errorOccurred.emit(f"❌ Seri Port Hatası: {e}")
                    self._is_running = False # Stop on error
                    break
                # --- Handle Other Unexpected Errors ---
                except Exception as e:
                    if self._is_running:
                        print(f"ERROR: Worker.run - Unexpected error in loop: {e}")
                        traceback.print_exc()
                        self.errorOccurred.emit(f"❌ Okuma döngüsü hatası: {e}")
                    self._is_running = False # Stop on error
                    break

                # --- Yield thread execution ---
                time.sleep(LOOP_SLEEP)
            # --- End of while loop ---
            print("DEBUG: Worker.run - Loop finished.")

        # --- Handle Connection/Setup Errors ---
        except (serial.SerialException, ValueError, Exception) as e:
            print(f"ERROR: Worker.run - Connection/Setup failed for {self.port}: {e}")
            traceback.print_exc()
            self.errorOccurred.emit(f"❌ Bağlantı/Başlatma Hatası ({self.port}): {e}")
        # --- Cleanup ---
        finally:
            print("DEBUG: Worker.run: Finally block executing...")
            self._is_running = False
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    # ---- Zaman damgalı loglama ----
                    start_time = time.time()
                    print(f"DEBUG: Worker.run: {start_time:.3f} - Attempting to close serial port...")
                    self.serial_connection.close()
                    end_time = time.time()
                    print(f"DEBUG: Worker.run: {end_time:.3f} - Serial port closed (took {end_time - start_time:.3f}s).")
                    # ---- Loglama sonu ----
                except Exception as close_err:
                    print(f"ERROR: Worker.run: Exception during port close: {close_err}")
                    self.errorOccurred.emit(f"⚠️ Port kapatma hatası: {close_err}")
            print("DEBUG: Worker.run: Emitting final 'Bağlantı Kesildi'.")
            self.statusUpdate.emit("⚪ Bağlantı Kesildi")
            print("DEBUG: Worker.run: Worker execution finished.")

    def _process_line(self, line_bytes):
        """
        Processes a line of bytes received from the serial port.
        Decodes the line, checks for known prefixes (UID:, CMD:),
        parses the data, and emits the appropriate signal.
        """
        print(f"DEBUG: Worker._process_line - Raw: {line_bytes!r}")
        try:
            # Decode using ASCII (most common for microcontrollers), replace errors
            decoded_line = line_bytes.decode('ascii', errors='replace').strip()
            print(f"DEBUG: Worker._process_line - Decoded: '{decoded_line}'")

            if not decoded_line: return # Ignore empty lines after stripping

            # --- Check for UID Prefix ---
            if decoded_line.startswith(UID_PREFIX):
                uid_part = decoded_line[len(UID_PREFIX):].strip()
                # Clean UID: Remove non-alphanumeric, uppercase (handles spaces from ESP)
                cleaned_uid = "".join(filter(str.isalnum, uid_part)).upper()
                print(f"DEBUG: Worker._process_line - Detected UID. Cleaned: '{cleaned_uid}'")
                if cleaned_uid:
                    self.cardRead.emit(cleaned_uid)
                else:
                     print(f"WARN: Worker._process_line - Extracted UID part '{uid_part}' was empty after cleaning.")

            # --- Check for Acknowledgment Prefix ---
            elif decoded_line.startswith(ACK_PREFIX):
                 ack_command = decoded_line[len(ACK_PREFIX):].strip()
                 print(f"DEBUG: Worker._process_line - Detected ACK: '{ack_command}'")
                 self.commandAckReceived.emit(ack_command) # Emit the specific ACK received

            # --- Handle other potential lines ---
            else:
                # Could be debug messages from ESP or unknown responses
                print(f"DEBUG: Worker._process_line - Ignoring unrecognized line: '{decoded_line}'")

        except Exception as e:
            print(f"ERROR: Worker._process_line - Failed to process line: {e}")
            traceback.print_exc()
            self.errorOccurred.emit(f"⚠️ Gelen veri işlenemedi: {e}")

    @pyqtSlot()
    def stop(self):
        """Signals the worker's main loop (_is_running=False) to terminate gracefully."""
        print("DEBUG: Worker.stop - Stop requested.")
        self._is_running = False

    @pyqtSlot(str)
    def sendCommandSlot(self, command):
        """
        Slot callable from the controller thread (via signal/slot) to send
        a command string over the serial port.
        """
        print(f"DEBUG: Worker.sendCommandSlot - Received request to send: '{command}'")
        if self.serial_connection and self.serial_connection.is_open:
            if self._is_running: # Check if worker is active
                try:
                    # Append newline for ESP's readStringUntil or readline
                    full_command = command + '\n'
                    encoded_command = full_command.encode('ascii') # Encode as ASCII bytes

                    print(f"DEBUG: Worker.sendCommandSlot - Writing bytes: {encoded_command!r}")
                    self.serial_connection.write(encoded_command)
                    print(f"DEBUG: Worker.sendCommandSlot - Command '{command}' sent successfully.")
                except (serial.SerialTimeoutException, serial.SerialException, Exception) as e:
                    print(f"ERROR: Worker.sendCommandSlot - Failed to send command '{command}': {e}")
                    traceback.print_exc()
                    self.errorOccurred.emit(f"❌ Komut '{command}' gönderilemedi: {e}")
            else:
                 print("WARN: Worker.sendCommandSlot - Worker not running, command not sent.")
                 # self.errorOccurred.emit("❌ Komut gönderilemedi: Okuyucu aktif değil.") # Avoid spamming
        else:
            print("ERROR: Worker.sendCommandSlot - Serial connection not available.")
            self.errorOccurred.emit("❌ Komut gönderilemedi: Bağlantı yok.")


# ==============================================================================
# Controller Class - Manages Worker Thread and UI Interaction
# ==============================================================================
class CardReaderController(QObject):
    """
    Manages the CardReaderWorker thread and acts as an interface
    between the serial communication logic and the main application UI.
    """
    # --- Signals for UI ---
    cardRead = pyqtSignal(str)          # Relayed from worker
    statusUpdate = pyqtSignal(str)      # Relayed from worker
    errorOccurred = pyqtSignal(str)     # Relayed from worker
    commandAckReceived = pyqtSignal(str)# Relayed from worker

    # --- Internal Signal ---
    # Used to safely trigger the worker's sendCommandSlot from the controller thread
    _sendCommandToWorkerSignal = pyqtSignal(str)

    # --- Constants ---
    DISCONNECT_WAIT_TIMEOUT = 5000 # Milliseconds to wait for thread graceful finish

    def __init__(self, parent=None):
        """Initializes the controller."""
        super().__init__(parent)
        self.worker = None
        self.thread = None
        self._is_connected = False # Internal connection state flag
        print("DEBUG: Controller.__init__ - Initialized.")

    @staticmethod
    def list_ports():
        """Returns a list of available serial port device names."""
        print("DEBUG: Controller.list_ports - Requesting port list...")
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [port.device for port in ports]
            print(f"DEBUG: Controller.list_ports - Found: {port_list}")
            return port_list
        except Exception as e:
            print(f"ERROR: Controller.list_ports - Failed: {e}")
            return []

    # Keep previous connect signatures for flexibility
    @pyqtSlot(str, int)
    @pyqtSlot(str)
    def connect(self, port_name, baud_rate=ESP_BAUD_RATE):
        """
        Starts the connection process by creating and starting the worker thread.
        """
        print(f"DEBUG: Controller.connect - Request for {port_name} @ {baud_rate} bps")
        if self.is_connected():
            self.errorOccurred.emit("⚠️ Zaten başka bir porta bağlı.")
            print("DEBUG: Controller.connect - Already connected.")
            return
        if not port_name:
            self.errorOccurred.emit("⚠️ Lütfen bir seri port seçin.")
            print("DEBUG: Controller.connect - No port selected.")
            return

        self.statusUpdate.emit(f"🟡 Bağlanılıyor: {port_name}...")
        print("DEBUG: Controller.connect - Creating Thread & Worker...")
        self.thread = QThread(self)
        self.worker = CardReaderWorker(port=port_name, baud_rate=baud_rate)
        self.worker.moveToThread(self.thread)

# --- Connect signals ---
        # Worker -> Controller/UI
        self.worker.cardRead.connect(self.cardRead)
        self.worker.statusUpdate.connect(self._handle_worker_status)
        self.worker.errorOccurred.connect(self.errorOccurred)
        self.worker.commandAckReceived.connect(self.commandAckReceived)

        # Internal Controller signal -> Worker Slot
        self._sendCommandToWorkerSignal.connect(self.worker.sendCommandSlot)

        # Thread -> Worker/Controller
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self._on_thread_finished) # Slot for additional cleanup/logging

        # ---- OTOMATİK TEMİZLEME BAĞLANTILARI ----
        # Thread bittiğinde hem worker'ı hem de thread'i silmek üzere işaretle
        # self.worker.finished.connect(self.worker.deleteLater) # <-- BU SATIRI SİLİN VEYA YORUM YAPIN
        self.thread.finished.connect(self.worker.deleteLater)  # <-- DOĞRU BAĞLANTI: Thread bitince worker'ı sil
        self.thread.finished.connect(self.thread.deleteLater)  # <-- DOĞRU BAĞLANTI: Thread bitince thread'i sil

        print("DEBUG: Controller.connect - Starting thread...")
        self.thread.start()

    @pyqtSlot(str)
    def _handle_worker_status(self, message):
        """Processes status messages from the worker, updates internal state."""
        print(f"DEBUG: Controller._handle_worker_status - Received: '{message}'")
        # Update state based on definitive messages
        if message.startswith("✅ Bağlandı:"):
            self._is_connected = True
            print("DEBUG: Controller - State set to CONNECTED.")
        elif message == "⚪ Bağlantı Kesildi":
             self._is_connected = False
             print("DEBUG: Controller - State set to DISCONNECTED.")
        self.statusUpdate.emit(message) # Relay to UI

    @pyqtSlot()
    def disconnect(self):
        """Initiates graceful disconnection."""
        print("DEBUG: Controller.disconnect - Request received.")
        if not self.thread or not self.thread.isRunning():
            print("DEBUG: Controller.disconnect - Not connected or thread not running.")
            self._is_connected = False # Ensure state is correct
            return

        print("DEBUG: Controller.disconnect - Signaling worker to stop...")
        self.statusUpdate.emit("🟡 Bağlantı kesiliyor...")
        if self.worker:
            # Safely invoke stop slot on worker thread
            QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)
        else:
             print("WARN: Controller.disconnect - Worker object missing.")

        # --- Wait for thread to finish ---
        print("DEBUG: Controller.disconnect - Requesting thread quit...")
        if self.thread: # Check if thread object exists
            self.thread.quit() # Ask event loop (if any) to exit
            print(f"DEBUG: Controller.disconnect - Waiting max {self.DISCONNECT_WAIT_TIMEOUT}ms for thread...")
            wait_success = self.thread.wait(self.DISCONNECT_WAIT_TIMEOUT)

            if not wait_success:
                print(f"ERROR: Controller.disconnect - Thread wait timed out!")
                self.errorOccurred.emit("⚠️ Okuyucu thread zamanında durmadı!")
                # ** AVOID TERMINATE **
            else:
                print("DEBUG: Controller.disconnect - Thread finished gracefully.")
        else:
             print("WARN: Controller.disconnect - Thread object missing during wait.")

        # --- Final state update ---
        self._is_connected = False # Ensure state is false after disconnect attempt
        print("DEBUG: Controller.disconnect - State set to DISCONNECTED.")
        # Worker's finally block should emit the final "Bağlantı Kesildi" status

    @pyqtSlot()
    def _on_thread_finished(self):
        """Cleans up references when the thread's finished signal is emitted."""
        print("DEBUG: Controller._on_thread_finished - Signal received.")
        self._is_connected = False # Ensure state is false
        # Clear references; deleteLater should handle actual object deletion
        self.thread = None
        self.worker = None
        print("DEBUG: Controller._on_thread_finished - Cleanup complete.")

    def is_connected(self):
        """Returns True if the connection is believed to be active."""
        # Check internal flag and thread status
        return self._is_connected and self.thread and self.thread.isRunning()

    @pyqtSlot(str)
    def send_command(self, command):
         """
         Public slot/method to send a command to the ESP32 via the worker thread.
         """
         print(f"DEBUG: Controller.send_command - Request to send: '{command}'")
         if self.is_connected() and self.worker:
             # Emit the internal signal which is connected to the worker's slot
             self._sendCommandToWorkerSignal.emit(command)
             print(f"DEBUG: Controller.send_command - Signal emitted to worker.")
         else:
              print(f"WARN: Controller.send_command - Cannot send '{command}', not connected.")
              self.errorOccurred.emit(f"❌ Komut '{command}' gönderilemedi: Bağlantı yok.")

    # --- Convenience method for UI ---
    @pyqtSlot()
    def system_check(self):
        """Sends the predefined system check command."""
        print("DEBUG: Controller.system_check - Requesting check.")
        self.send_command(CMD_SYSTEM_CHECK)

    def cleanup(self):
        """Called on application exit to ensure disconnection."""
        print("DEBUG: Controller.cleanup - Initiating...")
        self.disconnect() # Request disconnect
        # Brief wait for cleanup signals/slots
        if self.thread:
             print("DEBUG: Controller.cleanup - Waiting briefly...")
             self.thread.wait(100)
        print("DEBUG: Controller.cleanup - Finished.")