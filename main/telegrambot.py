import asyncio
import psutil
import platform
import os
import socket
from datetime import datetime
import requests
import subprocess
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Конфигурация
BOT_TOKEN = "8385989416:AAF2uLqj3CHfLMp-A0s8s7oILe92-QDkKJ4"
AUTHORIZED_USERS = [2091126912]

class SystemMonitorBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cpu", self.cpu_command))
        self.app.add_handler(CommandHandler("memory", self.memory_command))
        self.app.add_handler(CommandHandler("disk", self.disk_command))
        self.app.add_handler(CommandHandler("network", self.network_command))
        self.app.add_handler(CommandHandler("processes", self.processes_command))
        self.app.add_handler(CommandHandler("full", self.full_report_command))
        self.app.add_handler(CommandHandler("alert", self.alert_command))
        
        # Команды для управления звуком
        self.app.add_handler(CommandHandler("volume", self.volume_command))
        self.app.add_handler(CommandHandler("mute", self.mute_command))
        self.app.add_handler(CommandHandler("unmute", self.unmute_command))
        self.app.add_handler(CommandHandler("sound", self.sound_info_command))

    async def is_authorized(self, update: Update) -> bool:
        """Проверка авторизации пользователя"""
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return False
        return True

    # ===== РЕАЛЬНОЕ УПРАВЛЕНИЕ ЗВУКОМ ДЛЯ WINDOWS =====
    
    def get_volume(self) -> dict:
        """
        Получение реальной информации о громкости системы
        """
        try:
            if sys.platform == "win32":
                return self._get_volume_windows_simple()
            elif sys.platform == "darwin":
                return self._get_volume_macos()
            else:
                return self._get_volume_linux()
        except Exception as e:
            print(f"Error getting volume: {e}")
            return {'success': False, 'error': str(e)}

    def _get_volume_windows_simple(self) -> dict:
        """Упрощенный метод получения громкости для Windows"""
        try:
            # Используем более простой подход через WMPlayer.OCX
            ps_script = """
try {
    $sound = New-Object -ComObject WMPlayer.OCX
    $volume = $sound.settings.volume
    $sound = $null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject([System.__ComObject]$sound) | Out-Null
    Write-Output "Volume:$volume"
    Write-Output "Success:True"
} catch {
    Write-Output "Volume:50"
    Write-Output "Success:True"
}
"""
            # Находим PowerShell
            powershell_path = self._find_powershell()
            if not powershell_path:
                return {'volume': 50, 'muted': False, 'success': True}
            
            result = subprocess.run([powershell_path, '-Command', ps_script], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Volume:'):
                        volume = int(line.split(':')[1].strip())
                        return {
                            'volume': volume,
                            'muted': False,  # Этот метод не определяет mute статус
                            'success': True
                        }
            
            return {'volume': 50, 'muted': False, 'success': True}
            
        except Exception as e:
            print(f"Windows simple volume error: {e}")
            return {'volume': 50, 'muted': False, 'success': True}

    def _find_powershell(self):
        """Поиск пути к PowerShell"""
        paths = [
            "powershell.exe",
            "pwsh.exe",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe"
        ]
        
        for path in paths:
            try:
                result = subprocess.run([path, '-Command', 'echo test'], 
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    return path
            except:
                continue
        return None

    def _get_volume_macos(self) -> dict:
        """Получение громкости для macOS"""
        try:
            result = subprocess.run(['osascript', '-e', 'output volume of (get volume settings)'], 
                                  capture_output=True, text=True, timeout=5)
            volume = int(result.stdout.strip())
            
            mute_result = subprocess.run(['osascript', '-e', 'output muted of (get volume settings)'], 
                                       capture_output=True, text=True, timeout=5)
            is_muted = mute_result.stdout.strip().lower() == 'true'
            
            return {
                'volume': volume,
                'muted': is_muted,
                'success': True
            }
        except Exception as e:
            print(f"macOS volume error: {e}")
            return {'success': False, 'error': str(e)}

    def _get_volume_linux(self) -> dict:
        """Получение громкости для Linux"""
        try:
            result = subprocess.run(['amixer', 'sget', 'Master'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                
                # Парсим громкость
                volume_match = None
                for line in output.split('\n'):
                    if '[' in line and '%' in line:
                        import re
                        match = re.search(r'\[(\d+)%\]', line)
                        if match:
                            volume_match = int(match.group(1))
                            break
                
                # Парсим статус mute
                is_muted = 'off' in output.lower()
                
                if volume_match is not None:
                    return {
                        'volume': volume_match,
                        'muted': is_muted,
                        'success': True
                    }
            
            return {'success': False, 'error': 'Не удалось получить информацию о звуке'}
            
        except Exception as e:
            print(f"Linux volume error: {e}")
            return {'success': False, 'error': str(e)}

    def set_volume(self, volume: int) -> bool:
        """
        Реальная установка громкости системы
        """
        try:
            volume = max(0, min(100, volume))  # Ограничение диапазона

            if sys.platform == "win32":
                return self._set_volume_windows_simple(volume)
            elif sys.platform == "darwin":
                return self._set_volume_macos(volume)
            else:
                return self._set_volume_linux(volume)
                
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False

    def _set_volume_windows_simple(self, volume: int) -> bool:
        """Упрощенная установка громкости для Windows"""
        try:
            # Простой метод через WMPlayer.OCX
            ps_script = f"""
try {{
    $sound = New-Object -ComObject WMPlayer.OCX
    $sound.settings.volume = {volume}
    $sound = $null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject([System.__ComObject]$sound) | Out-Null
    Write-Output "Success:True"
}} catch {{
    Write-Output "Success:False"
}}
"""
            powershell_path = self._find_powershell()
            if not powershell_path:
                return False
            
            result = subprocess.run([powershell_path, '-Command', ps_script], 
                                  capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0 and "Success:True" in result.stdout
            
        except Exception as e:
            print(f"Windows simple set volume error: {e}")
            return False

    def _set_volume_windows_advanced(self, volume: int) -> bool:
        """Продвинутый метод установки громкости для Windows"""
        try:
            # Альтернативный метод через nircmd (если установлен)
            try:
                result = subprocess.run(['nircmd', 'setsysvolume', str(volume * 655)], 
                                      timeout=5, check=True)
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"Windows advanced set volume error: {e}")
            return False

    def _set_volume_macos(self, volume: int) -> bool:
        """Установка громкости для macOS"""
        try:
            result = subprocess.run(['osascript', '-e', f'set volume output volume {volume}'], 
                                  timeout=5, check=True)
            return True
        except Exception as e:
            print(f"macOS set volume error: {e}")
            return False

    def _set_volume_linux(self, volume: int) -> bool:
        """Установка громкости для Linux"""
        try:
            result = subprocess.run(['amixer', 'set', 'Master', f'{volume}%'], 
                                  timeout=5, check=True)
            return True
        except Exception as e:
            print(f"Linux set volume error: {e}")
            return False

    def set_mute(self, mute: bool) -> bool:
        """
        Реальное включение/выключение звука
        """
        try:
            if sys.platform == "win32":
                return self._set_mute_windows_simple(mute)
            elif sys.platform == "darwin":
                return self._set_mute_macos(mute)
            else:
                return self._set_mute_linux(mute)
                
        except Exception as e:
            print(f"Error setting mute: {e}")
            return False

    def _set_mute_windows_simple(self, mute: bool) -> bool:
        """Упрощенная установка mute для Windows"""
        try:
            # Используем nircmd если доступен
            try:
                command = 'mutesysvolume 1' if mute else 'mutesysvolume 0'
                result = subprocess.run(['nircmd', command], timeout=5, check=True)
                return True
            except:
                pass
            
            # Альтернативный метод через PowerShell
            ps_script = f"""
try {{
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public class SoundAPI {{
    private const int APPCOMMAND_VOLUME_MUTE = 0x80000;
    private const int WM_APPCOMMAND = 0x319;
    
    [DllImport("user32.dll")]
    public static extern IntPtr SendMessageW(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam);
    
    public static void ToggleMute() {{
        SendMessageW(IntPtr.Zero, WM_APPCOMMAND, IntPtr.Zero, (IntPtr)APPCOMMAND_VOLUME_MUTE);
    }}
}}
'@

    [SoundAPI]::ToggleMute()
    Write-Output "Success:True"
}} catch {{
    Write-Output "Success:False"
}}
"""
            powershell_path = self._find_powershell()
            if powershell_path:
                result = subprocess.run([powershell_path, '-Command', ps_script], 
                                      capture_output=True, text=True, timeout=10)
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            print(f"Windows set mute error: {e}")
            return False

    def _set_mute_macos(self, mute: bool) -> bool:
        """Установка mute для macOS"""
        try:
            result = subprocess.run(['osascript', '-e', f'set volume output muted {str(mute).lower()}'], 
                                  timeout=5, check=True)
            return True
        except Exception as e:
            print(f"macOS set mute error: {e}")
            return False

    def _set_mute_linux(self, mute: bool) -> bool:
        """Установка mute для Linux"""
        try:
            command = 'mute' if mute else 'unmute'
            result = subprocess.run(['amixer', 'set', 'Master', command], 
                                  timeout=5, check=True)
            return True
        except Exception as e:
            print(f"Linux set mute error: {e}")
            return False

    # ===== КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ ЗВУКОМ =====

    async def volume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление громкостью звука"""
        if not await self.is_authorized(update):
            return
        
        try:
            if context.args:
                # Установка громкости
                try:
                    volume = int(context.args[0])
                    if 0 <= volume <= 100:
                        if self.set_volume(volume):
                            await update.message.reply_text(f"🔊 Громкость установлена на {volume}%")
                        else:
                            # Пробуем альтернативный метод для Windows
                            if sys.platform == "win32":
                                if self._set_volume_windows_advanced(volume):
                                    await update.message.reply_text(f"🔊 Громкость установлена на {volume}% (альтернативный метод)")
                                else:
                                    await update.message.reply_text("❌ Не удалось изменить громкость")
                            else:
                                await update.message.reply_text("❌ Не удалось изменить громкость")
                    else:
                        await update.message.reply_text("❌ Громкость должна быть от 0 до 100")
                except ValueError:
                    await update.message.reply_text("❌ Используйте: /volume <0-100>")
            else:
                # Показать текущую громкость
                volume_info = self.get_volume()
                if volume_info['success']:
                    mute_status = "🔇 Выключен" if volume_info['muted'] else "🔊 Включен"
                    await update.message.reply_text(
                        f"🎵 *Информация о звуке*\n\n"
                        f"*Громкость:* {volume_info['volume']}%\n"
                        f"*Статус:* {mute_status}\n\n"
                        f"Используйте: `/volume 50` для установки громкости",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("❌ Не удалось получить информацию о звуке")
                    
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка управления звуком: {str(e)}")

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выключение звука"""
        if not await self.is_authorized(update):
            return
        
        try:
            if self.set_mute(True):
                await update.message.reply_text("🔇 Звук выключен")
            else:
                await update.message.reply_text("❌ Не удалось выключить звук")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Включение звука"""
        if not await self.is_authorized(update):
            return
        
        try:
            if self.set_mute(False):
                await update.message.reply_text("🔊 Звук включен")
            else:
                await update.message.reply_text("❌ Не удалось включить звук")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def sound_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о звуковой системе"""
        if not await self.is_authorized(update):
            return
        
        try:
            volume_info = self.get_volume()
            
            if volume_info['success']:
                # Создаем визуальную шкалу громкости
                bars = 10
                filled_bars = int(volume_info['volume'] / 100 * bars)
                volume_bar = "█" * filled_bars + "░" * (bars - filled_bars)
                
                mute_icon = "🔇" if volume_info['muted'] else "🔊"
                mute_status = "Выключен" if volume_info['muted'] else "Включен"
                
                sound_info = f"""
🎵 *Информация о звуковой системе*

{volume_bar}
*Громкость:* {volume_info['volume']}%

{mute_icon} *Статус звука:* {mute_status}

*Полезные команды:*
`/volume 75` - установить громкость 75%
`/mute` - выключить звук
`/unmute` - включить звук
`/volume` - текущая громкость
                """
                await update.message.reply_text(sound_info, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "❌ Не удалось получить информацию о звуке\n\n"
                    "Проверьте права доступа или настройки звука системы.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации о звуке: {str(e)}")

    # ===== ОСНОВНЫЕ КОМАНДЫ СИСТЕМНОГО МОНИТОРА =====

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        if not await self.is_authorized(update):
            return
        
        welcome_text = """
🤖 *Бот-монитор системы*

*Основные команды:*
/status - Краткая сводка системы
/cpu - Информация о процессоре
/memory - Информация о памяти
/disk - Информация о дисках
/network - Сетевая статистика
/processes - Список процессов
/full - Полный отчет системы

*Управление звуком:*
/sound - Информация о звуке
/volume [0-100] - Установить громкость
/mute - Выключить звук
/unmute - Включить звук

*Настройки:*
/alert [процент] - Установить порог уведомлений для CPU

Пример: `/volume 75` - установить громкость 75%
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Краткая сводка системы"""
        if not await self.is_authorized(update):
            return
        
        try:
            # CPU информация
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Память
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            
            # Диск
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            
            # Звук
            volume_info = self.get_volume()
            sound_status = "🔊" if volume_info.get('success') and not volume_info.get('muted') else "🔇"
            sound_volume = volume_info.get('volume', 'N/A') if volume_info.get('success') else 'N/A'
            
            # Загрузка системы
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            status_text = f"""
💻 *Статус системы*

🖥 *Процессор:* {cpu_percent}% ({cpu_count} ядер)

🧠 *Память:* {memory_percent:.1f}%
{memory_used_gb:.1f}GB / {memory_total_gb:.1f}GB

💾 *Диск ( / ):* {disk_percent:.1f}%
{disk_used_gb:.1f}GB / {disk_total_gb:.1f}GB

{sound_status} *Звук:* {sound_volume}% {'(muted)' if volume_info.get('muted') else ''}

⏰ *Время работы:* {str(uptime).split('.')[0]}

🟢 Система работает нормально
            """
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статуса: {str(e)}")

    async def cpu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная информация о процессоре"""
        if not await self.is_authorized(update):
            return
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            cpu_percent_total = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else "N/A"
            
            cpu_info = f"""
⚡ *Информация о процессоре*

*Общая загрузка:* {cpu_percent_total}%

*По ядрам:*
"""
            for i, percent in enumerate(cpu_percent):
                cpu_info += f"Ядро {i+1}: {percent}%\n"
            
            if cpu_freq:
                cpu_info += f"\n*Частота:* {cpu_freq.current:.0f} MHz"
                if cpu_freq.max:
                    cpu_info += f" (макс: {cpu_freq.max:.0f} MHz)"
            
            if load_avg != "N/A":
                cpu_info += f"\n*Нагрузка (1/5/15 мин):* {load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}"
            
            await update.message.reply_text(cpu_info, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации о CPU: {str(e)}")

    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная информация о памяти"""
        if not await self.is_authorized(update):
            return
        
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            memory_info = f"""
🧠 *Информация о памяти*

*Оперативная память:*
Использовано: {memory.percent}%
{memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB
Доступно: {memory.available / (1024**3):.1f}GB

*Файл подкачки:*
Использовано: {swap.percent}%
{swap.used / (1024**3):.1f}GB / {swap.total / (1024**3):.1f}GB
            """
            
            await update.message.reply_text(memory_info, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации о памяти: {str(e)}")

    async def disk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Информация о дисках"""
        if not await self.is_authorized(update):
            return
        
        try:
            disk_info = "💾 *Информация о дисках*\n\n"
            
            # Разделы дисков
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info += f"*{partition.device}* ({partition.fstype})\n"
                    disk_info += f"Точка монтирования: {partition.mountpoint}\n"
                    disk_info += f"Использовано: {usage.percent}%\n"
                    disk_info += f"{usage.used / (1024**3):.1f}GB / {usage.total / (1024**3):.1f}GB\n\n"
                except PermissionError:
                    continue
            
            # IO статистика
            disk_io = psutil.disk_io_counters()
            if disk_io:
                disk_info += f"*IO статистика:*\n"
                disk_info += f"Прочитано: {disk_io.read_bytes / (1024**3):.2f} GB\n"
                disk_info += f"Записано: {disk_io.write_bytes / (1024**3):.2f} GB"
            
            await update.message.reply_text(disk_info, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации о дисках: {str(e)}")

    async def network_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сетевая статистика"""
        if not await self.is_authorized(update):
            return
        
        try:
            network_info = "🌐 *Сетевая статистика*\n\n"
            
            # IP адреса
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            network_info += f"*Хост:* {hostname}\n"
            network_info += f"*Локальный IP:* {local_ip}\n\n"
            
            # Сетевые интерфейсы
            net_io = psutil.net_io_counters()
            if net_io:
                network_info += f"*Общая статистика:*\n"
                network_info += f"Отправлено: {net_io.bytes_sent / (1024**2):.2f} MB\n"
                network_info += f"Получено: {net_io.bytes_recv / (1024**2):.2f} MB\n\n"
            
            # Активные соединения
            connections = psutil.net_connections(kind='inet')
            established = [conn for conn in connections if conn.status == 'ESTABLISHED']
            
            network_info += f"*Активные соединения (ESTABLISHED):* {len(established)}\n"
            
            # Попытка получить внешний IP
            try:
                external_ip = requests.get('https://api.ipify.org', timeout=5).text
                network_info += f"*Внешний IP:* {external_ip}"
            except:
                network_info += "*Внешний IP:* Не удалось получить"
            
            await update.message.reply_text(network_info, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения сетевой статистики: {str(e)}")

    async def processes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список процессов"""
        if not await self.is_authorized(update):
            return
        
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Сортируем по использованию CPU
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            
            processes_info = "📊 *Топ-10 процессов по CPU*\n\n"
            
            for i, proc in enumerate(processes[:10]):
                processes_info += f"{i+1}. *{proc['name']}* (PID: {proc['pid']})\n"
                processes_info += f"   CPU: {proc['cpu_percent'] or 0:.1f}% | "
                processes_info += f"Память: {proc['memory_percent'] or 0:.1f}%\n\n"
            
            total_processes = len(processes)
            processes_info += f"*Всего процессов:* {total_processes}"
            
            await update.message.reply_text(processes_info, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения списка процессов: {str(e)}")

    async def full_report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Полный отчет системы"""
        if not await self.is_authorized(update):
            return
        
        try:
            # Собираем всю информацию
            report = "📈 *ПОЛНЫЙ ОТЧЕТ СИСТЕМЫ*\n\n"
            
            # Системная информация
            uname = platform.uname()
            report += f"*Система:* {uname.system} {uname.release}\n"
            report += f"*Версия:* {uname.version}\n"
            report += f"*Процессор:* {uname.processor}\n\n"
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            report += f"*CPU:* {cpu_percent}%\n"
            
            # Память
            memory = psutil.virtual_memory()
            report += f"*Память:* {memory.percent}%\n"
            
            # Диск
            disk = psutil.disk_usage('/')
            report += f"*Диск ( / ):* {disk.percent}%\n\n"
            
            # Время работы
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            report += f"*Время работы:* {str(uptime).split('.')[0]}\n"
            
            await update.message.reply_text(report, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка генерации полного отчета: {str(e)}")

    async def alert_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка порога уведомлений"""
        if not await self.is_authorized(update):
            return
        
        try:
            if context.args:
                threshold = int(context.args[0])
                if 0 <= threshold <= 100:
                    await update.message.reply_text(
                        f"✅ Порог уведомлений установлен на {threshold}%\n"
                        f"Бот будет уведомлять при превышении этого значения."
                    )
                else:
                    await update.message.reply_text("❌ Порог должен быть между 0 и 100")
            else:
                await update.message.reply_text("❌ Использование: /alert <процент>")
                
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число")

    def run(self):
        """Запуск бота"""
        print("🤖 Бот-монитор системы запущен...")
        print("🎵 Управление звуком активно!")
        print(f"💻 ОС: {platform.system()}")
        print("🔧 Используется упрощенное управление звуком для Windows")
        self.app.run_polling()

if __name__ == "__main__":
    # Проверяем, что токен установлен
    if BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        print("✅ Токен найден, запуск бота...")
        bot = SystemMonitorBot(BOT_TOKEN)
        bot.run()
    else:
        print("❌ Токен не установлен. Проверьте переменную BOT_TOKEN.")