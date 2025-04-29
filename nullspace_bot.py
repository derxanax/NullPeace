import re
import io
import os
import base64
import logging
import colorlog
import tempfile
import sys
from PIL import Image, ImageSequence
from telegram import Update, ReplyKeyboardMarkup, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

try:
    import moviepy
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
    logger = logging.getLogger()
    logger.info(f"MoviePy успешно загружен: {moviepy.__version__}")
except ImportError as e:
    MOVIEPY_AVAILABLE = False
    logger = logging.getLogger()
    logger.warning(f"Ошибка импорта MoviePy: {e}. Пути Python: {sys.path}")
    logger.warning("Для работы с анимациями установите: pip install moviepy")

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)s%(reset)s: %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = [handler]

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

ZWSP = '\u200B' 
ZWNJ = '\u200C'  
ZWBSP = '\u2060'  
ZWNBSP = '\uFEFF'  

PREFIX = "пр"

IMAGE_PREFIX = f"{PREFIX}IMG"

GIF_PREFIX = f"{PREFIX}GIF"

DEFAULT_KEY = 5

IMAGE_SIZE = (150, 150)  
IMAGE_QUALITY = 100     
MAX_IMAGE_DIMENSION = 150  

GIF_SIZE = (50, 50)    
GIF_FPS = 5            
GIF_DURATION = 200     

MAX_MESSAGE_LENGTH = 4096

USER_STATES = {}

PART_PATTERN = re.compile(r'Часть (\d+)/(\d+):')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

# клава


    keyboard = [
        ['🔒 Зашифровать', '🔓 Расшифровать'],
        ['📸 Зашифровать img (GIF/PNG)', '🔍 О боте']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    #текст старта но хуль обьяснять \
    
    await update.message.reply_text(
        'Привет! Я бот для шифрования сообщений с помощью NullsPace 🔐\n\n'
        '💬 <b>Просто напиши мне текст</b>, и я его зашифрую!\n'
        f'📋 А если пришлёшь зашифрованное сообщение (начинается с "{PREFIX}"), я его расшифрую.\n'
        '🖼️ Отправь фото или GIF и получи зашифрованную версию.\n'
        '🔄 Автоматическая расшифровка при копировании полного сообщения с префиксом.\n\n'
        '🔍 Выбери действие:',
        parse_mode='HTML',
        reply_markup=reply_markup
    )

def char_to_binary(char, key):

    char_code = ord(char) ^ key
    
    binary = format(char_code, '016b')
    
    return binary

def binary_to_char(binary, key):

    try:

        char_code = int(binary, 2)
        

        original_code = char_code ^ key
        

        return chr(original_code)
    except:
        return None

def encode_text(text: str) -> str:

    if not text:
        return PREFIX + ZWNBSP
    
    result = [PREFIX]
    key = DEFAULT_KEY
    

    i = 0
    while i < len(text):
        if i + 1 < len(text):

            char1 = text[i]
            char2 = text[i+1]
            code1 = ord(char1) ^ key
            code2 = ord(char2) ^ key
            

            bitlen1 = (code1.bit_length() + 7) // 8 * 8
            bitlen2 = (code2.bit_length() + 7) // 8 * 8
            

            binary1 = format(code1, f'0{bitlen1}b')
            binary2 = format(code2, f'0{bitlen2}b')
            

            zw_encoded1 = ''.join([ZWSP if bit == '0' else ZWNJ for bit in binary1])
            zw_encoded2 = ''.join([ZWSP if bit == '0' else ZWNJ for bit in binary2])
            

            result.append(zw_encoded1 + zw_encoded2 + ZWBSP)
            i += 2
        else:

            char = text[i]

            char_code = ord(char) ^ key
            
            
            bitlen = (char_code.bit_length() + 7) // 8 * 8
            

            binary = format(char_code, f'0{bitlen}b')
            

            zw_encoded = ''.join([ZWSP if bit == '0' else ZWNJ for bit in binary])
            result.append(zw_encoded + ZWBSP)
            i += 1
    

    result.append(ZWNBSP)
    
    return ''.join(result)

def decode_text(text: str) -> str:

    result = []
    key = DEFAULT_KEY
    

    if text.startswith(IMAGE_PREFIX):
        return decode_image(text)
    elif text.startswith(GIF_PREFIX):
        return decode_gif(text)
    

    if not text.startswith(PREFIX):
        return ""
    

    text = text[len(PREFIX):].replace(ZWNBSP, '')
    

    parts = text.split(ZWBSP)
    
    for part in parts:
        if not part:
            continue
        

        binary_sequence = ''.join(['0' if c == ZWSP else '1' for c in part])
        

        if len(binary_sequence) >= 16 and len(binary_sequence) % 8 == 0:
            try:

                if len(binary_sequence) >= 16:

                    possible_splits = []
                    

                    for split_point in range(8, len(binary_sequence), 8):
                        binary1 = binary_sequence[:split_point]
                        binary2 = binary_sequence[split_point:]
                        
                        try:
                            char1 = chr(int(binary1, 2) ^ key)
                            char2 = chr(int(binary2, 2) ^ key)
                            

                            is_valid_char1 = (('а' <= char1.lower() <= 'я') or 
                                             ('a' <= char1.lower() <= 'z') or 
                                             ('0' <= char1 <= '9') or
                                             char1 == ' ' or
                                             char1 in '.,:;!?()[]{}@#$%^&*-_+=<>/\\\'\"')
                            
                            is_valid_char2 = (('а' <= char2.lower() <= 'я') or 
                                             ('a' <= char2.lower() <= 'z') or 
                                             ('0' <= char2 <= '9') or
                                             char2 == ' ' or
                                             char2 in '.,:;!?()[]{}@#$%^&*-_+=<>/\\\'\"')
                            
                            if is_valid_char1 and is_valid_char2:
                                possible_splits.append((char1, char2))
                        except:
                            continue
                    

                    if possible_splits:

                        result.extend(possible_splits[0])
                        continue
            except:
                pass
        

        try:
            char_code = int(binary_sequence, 2)
            original_code = char_code ^ key
            char = chr(original_code)
            

            is_valid_char = (('а' <= char.lower() <= 'я') or 
                             ('a' <= char.lower() <= 'z') or 
                             ('0' <= char <= '9') or
                             char == ' ' or
                             char in '.,:;!?()[]{}@#$%^&*-_+=<>/\\\'\"')
            
            if is_valid_char:
                result.append(char)
        except:

            pass
    
    return ''.join(result)

def resize_and_compress_image(photo_bytes):

    try:

        image = Image.open(io.BytesIO(photo_bytes))
        

        if hasattr(image, 'is_animated') and image.is_animated:
            return resize_gif(photo_bytes)
        

        width, height = image.size
        if width > height:
            new_width = min(width, MAX_IMAGE_DIMENSION)
            new_height = int(height * (new_width / width))
        else:
            new_height = min(height, MAX_IMAGE_DIMENSION)
            new_width = int(width * (new_height / height))
        

        image = image.resize((new_width, new_height), Image.LANCZOS)
        

        if image.mode == 'RGBA':
            image = image.convert('RGB')
        

        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', compress_level=0)
        output_buffer.seek(0)
        
        return output_buffer.getvalue()
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return None

def resize_gif(gif_bytes, is_mp4=False):

    try:

        logger.info(f"Получены байты {'MP4' if is_mp4 else 'GIF'}: {len(gif_bytes)} байт")
        

        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4' if is_mp4 else '.gif')
        temp_input.write(gif_bytes)
        temp_input.close()
        
        output_path = "temp_processed_gif.gif"
        
        if is_mp4 and MOVIEPY_AVAILABLE:

            logger.info(f"Конвертируем MP4 в GIF: {temp_input.name}")
            try:

                clip = VideoFileClip(temp_input.name)
                logger.info(f"Видео открыто: size={clip.size}, duration={clip.duration}s, fps={clip.fps}")
                

                width, height = clip.size
                if width > height:
                    new_width = min(width, GIF_SIZE[0])
                    new_height = int(height * (new_width / width))
                else:
                    new_height = min(height, GIF_SIZE[1])
                    new_width = int(width * (new_height / height))
                

                logger.info(f"Изменяем размер видео до {new_width}x{new_height}")
                

                resized_clip = clip.resized((new_width, new_height))
                

                logger.info(f"Устанавливаем частоту кадров при сохранении: {GIF_FPS} FPS")
                

                logger.info(f"Сохраняем как GIF: {output_path}")
                resized_clip.write_gif(output_path, fps=GIF_FPS)
                

                resized_clip.close()
                clip.close()
                

                with open(output_path, 'rb') as f:
                    processed_bytes = f.read()
                
                logger.info(f"MP4 успешно конвертирован в GIF, размер: {len(processed_bytes)} байт")
                

                os.unlink(temp_input.name)
                
                return processed_bytes
            except Exception as e:
                logger.error(f"Ошибка при конвертации MP4 в GIF: {str(e)}", exc_info=True)
        

        

        try:

            gif = Image.open(temp_input.name)
            

            logger.info(f"Открыт файл: формат={gif.format}, размер={gif.size}, режим={gif.mode}")
            

            is_animated = getattr(gif, "is_animated", False)
            logger.info(f"Файл анимирован: {is_animated}")
            
            if not is_animated:

                logger.info("Обрабатываем как статичное изображение")
                result = resize_and_compress_image(gif_bytes)
                os.unlink(temp_input.name)
                return result
            

            frames = []
            durations = []
            

            for i, frame in enumerate(ImageSequence.Iterator(gif)):
                logger.info(f"Обрабатываем кадр {i+1}")
                

                frame_copy = frame.copy()
                

                width, height = frame_copy.size
                if width > height:
                    new_width = min(width, GIF_SIZE[0])
                    new_height = int(height * (new_width / width))
                else:
                    new_height = min(height, GIF_SIZE[1])
                    new_width = int(width * (new_height / height))
                

                frame_resized = frame_copy.resize((new_width, new_height), Image.LANCZOS)
                

                if frame_resized.mode == 'RGBA':
                    frame_resized = frame_resized.convert('P', palette=Image.ADAPTIVE)
                elif frame_resized.mode not in ['P']:
                    frame_resized = frame_resized.convert('P', palette=Image.ADAPTIVE)
                

                frames.append(frame_resized)
                

                try:
                    duration = frame.info.get('duration', GIF_DURATION)
                    durations.append(duration)
                except:
                    durations.append(GIF_DURATION)
            
            logger.info(f"Обработано кадров: {len(frames)}")
            

            frames[0].save(
                output_path,
                format='GIF',
                save_all=True,
                append_images=frames[1:],
                optimize=False,
                duration=GIF_DURATION,
                loop=0
            )
            

            with open(output_path, 'rb') as f:
                processed_bytes = f.read()
            
            logger.info(f"GIF успешно обработан, размер: {len(processed_bytes)} байт")
            

            os.unlink(temp_input.name)
            
            return processed_bytes
        except Exception as e:
            logger.error(f"Ошибка при обработке через PIL: {str(e)}", exc_info=True)
            os.unlink(temp_input.name)
            return None
    except Exception as e:
        logger.error(f"Общая ошибка при обработке анимации: {str(e)}", exc_info=True)
        return None

def optimize_base64(base64_string):


    return base64_string

def encode_image(photo_bytes, is_gif=False):


    if is_gif:
        processed = resize_gif(photo_bytes)
        prefix = GIF_PREFIX
    else:
        processed = resize_and_compress_image(photo_bytes)
        prefix = IMAGE_PREFIX
    
    if not processed:
        return None
    

    base64_encoded = base64.b64encode(processed).decode('utf-8')
    

    base64_encoded = optimize_base64(base64_encoded)
    

    file_path = "temp_encoded_image.txt"
    

    result = [prefix]
    key = DEFAULT_KEY
    
    for char in base64_encoded:

        binary = char_to_binary(char, key)
        

        zw_encoded = ''.join([ZWSP if bit == '0' else ZWNJ for bit in binary])
        

        result.append(zw_encoded + ZWBSP)
    

    result.append(ZWNBSP)
    
    encoded_image = ''.join(result)
    

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(encoded_image)
    
    return encoded_image, file_path

def decode_image(text):

    try:
        key = DEFAULT_KEY
        

        text = text[len(IMAGE_PREFIX):].replace(ZWNBSP, '')
        

        parts = text.split(ZWBSP)
        
        base64_chars = []
        
        for part in parts:
            if not part:
                continue
            

            binary = ''.join(['0' if c == ZWSP else '1' for c in part])
            

            if len(binary) != 16:
                continue
            

            char = binary_to_char(binary, key)
            if char:
                base64_chars.append(char)
        

        base64_str = ''.join(base64_chars)
        

        image_bytes = base64.b64decode(base64_str)
        
        return image_bytes
    except Exception as e:
        logger.error(f"Ошибка при расшифровке изображения: {e}")
        return None

def decode_gif(text):

    try:
        key = DEFAULT_KEY
        

        text = text[len(GIF_PREFIX):].replace(ZWNBSP, '')
        

        parts = text.split(ZWBSP)
        
        base64_chars = []
        
        for part in parts:
            if not part:
                continue
            

            binary = ''.join(['0' if c == ZWSP else '1' for c in part])
            

            if len(binary) != 16:
                continue
            

            char = binary_to_char(binary, key)
            if char:
                base64_chars.append(char)
        

        base64_str = ''.join(base64_chars)
        

        gif_bytes = base64.b64decode(base64_str)
        
        return gif_bytes
    except Exception as e:
        logger.error(f"Ошибка при расшифровке GIF: {e}")
        return None

def split_message(text, max_length=MAX_MESSAGE_LENGTH):

    parts = []
    

    if len(text) <= max_length:
        return [text]
    

    prefix = ""
    if text.startswith('🔒 Зашифрованное сообщение:'):
        lines = text.split('\n', 1)
        if len(lines) > 1:
            prefix = lines[0] + '\n'
            text = lines[1]
    


    effective_max_length = max_length - len(prefix) - 20
    

    content_prefix = ""
    if text.startswith(PREFIX):
        content_prefix = PREFIX
        text = text[len(PREFIX):]
    

    current_length = 0
    current_part = content_prefix
    
    for char in text:

        if current_length >= effective_max_length:
            parts.append(current_part)
            current_part = content_prefix + char
            current_length = len(char)
        else:
            current_part += char
            current_length += 1
    

    if current_part and current_part != content_prefix:
        parts.append(current_part)
    

    for i in range(len(parts)):
        parts[i] = prefix + parts[i]
    
    return parts

def combine_message_parts(parts_dict):


    total_parts = len(parts_dict)
    

    if total_parts == 0:
        return ""
    

    sorted_parts = sorted(parts_dict.items(), key=lambda x: x[0])
    

    result = ""
    for part_num, part_text in sorted_parts:

        lines = part_text.split('\n', 2)
        if len(lines) > 1:

            encrypted_text = lines[1].strip()
            result += encrypted_text
    
    return result

async def ask_for_split_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, encoded_text: str):


    parts = split_message(f'🔒 Зашифрованное сообщение:\n{encoded_text}')
    parts_count = len(parts)
    

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, разделить", callback_data=f"split_yes_{len(encoded_text)}"),
            InlineKeyboardButton("❌ Нет", callback_data="split_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    

    await update.message.reply_text(
        f'⚠️ Сообщение получилось слишком большим ({len(encoded_text)} символов).\n'
        f'Максимальный размер сообщения в Telegram - {MAX_MESSAGE_LENGTH} символов.\n'
        f'Разделить на {parts_count} сообщений?',
        reply_markup=reply_markup
    )
    

    if 'user_data' not in context.bot_data:
        context.bot_data['user_data'] = {}
    
    context.bot_data['user_data'][update.effective_user.id] = {
        'encoded_text': encoded_text,
        'original_message': update.message
    }

async def handle_split_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    

    data = query.data
    

    if data == "split_no":
        await query.edit_message_text("❌ Операция отменена. Сообщение не было отправлено из-за превышения лимита.")
        return
    

    if data.startswith("split_yes_"):

        user_id = update.effective_user.id
        if 'user_data' in context.bot_data and user_id in context.bot_data['user_data']:
            encoded_text = context.bot_data['user_data'][user_id]['encoded_text']
            original_message = context.bot_data['user_data'][user_id]['original_message']
            

            full_message = f'🔒 Зашифрованное сообщение:\n{encoded_text}'
            message_parts = split_message(full_message)
            

            await query.edit_message_text(f"✅ Отправляю сообщение в {len(message_parts)} частях...")
            

            error_occurred = False
            
            try:

                for i, part in enumerate(message_parts):

                    if len(part) <= MAX_MESSAGE_LENGTH:

                        if len(message_parts) > 1:
                            part_label = f"Часть {i+1}/{len(message_parts)}: "

                            if len(part) + len(part_label) <= MAX_MESSAGE_LENGTH:
                                await original_message.reply_text(f"{part_label}{part}")
                            else:
                                await original_message.reply_text(part)
                        else:
                            await original_message.reply_text(part)
                    else:
                        logger.error(f"Часть {i+1} слишком длинная: {len(part)} символов")
                        error_occurred = True
                        break
                

                if not error_occurred:
                    await original_message.reply_text(
                        '📋 <b>Как расшифровать разделенное сообщение:</b>\n\n'
                        '1️⃣ <b>Вариант 1 (автоматически):</b>\n'
                        '   - Отправьте боту все части сообщения в любом порядке\n'
                        '   - Бот автоматически объединит части и расшифрует их\n\n'
                        '2️⃣ <b>Вариант 2 (вручную):</b>\n'
                        '   - Отправьте части собеседнику\n'
                        '   - Собеседник должен переслать эти части боту',
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке частей сообщения: {str(e)}", exc_info=True)
                await query.edit_message_text(f"❌ Произошла ошибка при отправке сообщения: {str(e)}")
            

            if error_occurred:
                await original_message.reply_text('❌ Не удалось разделить сообщение. Попробуйте отправить меньший текст или используйте файл.')
            

            del context.bot_data['user_data'][user_id]
        else:
            await query.edit_message_text("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    text = update.message.text
    

    part_match = PART_PATTERN.search(text)
    if part_match:
        part_num = int(part_match.group(1))
        total_parts = int(part_match.group(2))
        

        if user_id not in USER_STATES:
            USER_STATES[user_id] = {}
        
        if 'message_parts' not in USER_STATES[user_id]:
            USER_STATES[user_id]['message_parts'] = {}
            USER_STATES[user_id]['message_parts_total'] = total_parts
            await update.message.reply_text(f'🔄 Получена часть {part_num}/{total_parts}. Отправьте все части для расшифровки.')
        

        USER_STATES[user_id]['message_parts'][part_num] = text
        

        if len(USER_STATES[user_id]['message_parts']) == USER_STATES[user_id]['message_parts_total']:

            combined = combine_message_parts(USER_STATES[user_id]['message_parts'])
            

            if combined.startswith(PREFIX) and (ZWSP in combined or ZWNJ in combined):
                await update.message.reply_text('🔄 Расшифровываю объединенное сообщение из всех частей...')
                

                if combined.startswith(IMAGE_PREFIX):

                    image_bytes = decode_image(combined)
                    if image_bytes:

                        await update.message.reply_photo(
                            photo=io.BytesIO(image_bytes),
                            caption='🔓 Расшифрованное изображение из составных частей'
                        )
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать изображение из составных частей.')
                
                elif combined.startswith(GIF_PREFIX):

                    gif_bytes = decode_gif(combined)
                    if gif_bytes:

                        temp_gif = tempfile.NamedTemporaryFile(delete=False, suffix='.gif')
                        temp_gif.write(gif_bytes)
                        temp_gif.close()
                        

                        try:
                            await update.message.reply_animation(
                                animation=open(temp_gif.name, 'rb'),
                                caption='🔓 Расшифрованная GIF-анимация из составных частей'
                            )
                            os.unlink(temp_gif.name)
                        except Exception as e:
                            logger.error(f"Ошибка при отправке анимации: {str(e)}")
                            await update.message.reply_document(
                                document=open(temp_gif.name, 'rb'),
                                filename="decrypted_animation.gif",
                                caption='🔓 Расшифрованная GIF-анимация из составных частей (как файл)'
                            )
                            os.unlink(temp_gif.name)
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать GIF-анимацию из составных частей.')
                
                else:

                    decoded = decode_text(combined)
                    if decoded:
                        await update.message.reply_text(f'🔓 Расшифрованное сообщение из {total_parts} частей:\n{decoded}')
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать сообщение из составных частей.')
            

            del USER_STATES[user_id]['message_parts']
            del USER_STATES[user_id]['message_parts_total']
            
        else:

            remaining = USER_STATES[user_id]['message_parts_total'] - len(USER_STATES[user_id]['message_parts'])
            await update.message.reply_text(f'✅ Часть {part_num}/{total_parts} получена. Осталось получить {remaining} частей.')
        
        return
    #основа выше типо щас обработчики будут всякие )

    if text == '🔒 Зашифровать':
        await update.message.reply_text('Введите текст для шифрования:')
        return
    
    if text == '🔓 Расшифровать':
        await update.message.reply_text(
            f'Для расшифровки есть четыре способа:\n\n'
            f'1️⃣ Пришлите текст, начинающийся с "{PREFIX}"\n'
            f'2️⃣ Перешлите сообщение с зашифрованным текстом\n'
            f'3️⃣ Загрузите файл со скрытым содержимым\n'
            f'4️⃣ Отправьте поочередно все части разделенного сообщения'
        )
        return
    
    if text == '📸 Зашифровать img (GIF/PNG)':

        if user_id not in USER_STATES:
            USER_STATES[user_id] = {}
        USER_STATES[user_id]['waiting_for_photo'] = True
        
        await update.message.reply_text('Отправьте фотографию или GIF, которые хотите зашифровать:')
        return
    
    if text == '🔍 О боте':
        await update.message.reply_text(
            '🔐 <b>NullsPace Steganography Bot</b>\n\n'
            '🤫 Этот бот шифрует сообщения с помощью невидимых zero-width символов.\n'
            '🔍 Зашифрованное сообщение выглядит как обычный текст "пр".\n'
            '🖼️ Поддерживает шифрование изображений (до 150×150 пикселей в PNG)!\n'
            '🎞️ Также шифрует GIF-анимации (50×50, 5 FPS)!\n\n'
            '📝 <b>Как использовать:</b>\n'
            '1. Напишите любой текст → получите шифр\n'
            '2. Отправьте фото или GIF → получите зашифрованную версию\n'
            '3. Отправьте боту шифр → получите исходный текст/фото/GIF\n'
            '4. Если скопировано "🔒 Зашифрованное сообщение:" с "пр" → бот автоматически расшифрует\n'
            '5. Для больших сообщений, разделенных на части → отправьте все части боту и он соберет их\n\n'
            '⚠️ <b>Внимание:</b> Файлы с изображениями могут быть большими из-за высокого качества\n\n'
            '⚙️ <b>Технология:</b> Стеганография с использованием zero-width символов Unicode и XOR шифрование',
            parse_mode='HTML'
        )
        return
    

    if text.startswith(PREFIX) and (ZWSP in text or ZWNJ in text):

        if text.startswith(IMAGE_PREFIX):
            await update.message.reply_text('🔄 Расшифровываю изображение...')

            image_bytes = decode_image(text)
            if image_bytes:

                await update.message.reply_photo(
                    photo=io.BytesIO(image_bytes),
                    caption='🔓 Расшифрованное изображение высокого качества'
                )
            else:
                await update.message.reply_text('❌ Не удалось расшифровать изображение.')

        elif text.startswith(GIF_PREFIX):
            await update.message.reply_text('🔄 Расшифровываю GIF-анимацию...')

            gif_bytes = decode_gif(text)
            if gif_bytes:

                temp_gif = tempfile.NamedTemporaryFile(delete=False, suffix='.gif')
                temp_gif.write(gif_bytes)
                temp_gif.close()
                

                try:
                    await update.message.reply_animation(
                        animation=open(temp_gif.name, 'rb'),
                        caption='🔓 Расшифрованная GIF-анимация'
                    )

                    os.unlink(temp_gif.name)
                except Exception as e:
                    logger.error(f"Ошибка при отправке анимации: {str(e)}")

                    await update.message.reply_document(
                        document=open(temp_gif.name, 'rb'),
                        filename="decrypted_animation.gif",
                        caption='🔓 Расшифрованная GIF-анимация (как файл)'
                    )

                    os.unlink(temp_gif.name)
            else:
                await update.message.reply_text('❌ Не удалось расшифровать GIF-анимацию.')
        else:

            decoded = decode_text(text)
            if decoded:
                await update.message.reply_text(f'🔓 Расшифрованное сообщение:\n{decoded}')
            else:
                await update.message.reply_text('❌ Не удалось расшифровать сообщение.')

    elif text.startswith('🔒 Зашифрованное сообщение:'):

        lines = text.split('\n')
        if len(lines) > 1:
            encrypted_text = lines[1]
            

            if encrypted_text.startswith(PREFIX) and (ZWSP in encrypted_text or ZWNJ in encrypted_text):

                if encrypted_text.startswith(IMAGE_PREFIX):
                    await update.message.reply_text('🔄 Расшифровываю изображение...')
                    image_bytes = decode_image(encrypted_text)
                    if image_bytes:
                        await update.message.reply_photo(
                            photo=io.BytesIO(image_bytes),
                            caption='🔓 Расшифрованное изображение высокого качества'
                        )
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать изображение.')
                elif encrypted_text.startswith(GIF_PREFIX):
                    await update.message.reply_text('🔄 Расшифровываю GIF-анимацию...')
                    gif_bytes = decode_gif(encrypted_text)
                    if gif_bytes:
                        temp_gif = tempfile.NamedTemporaryFile(delete=False, suffix='.gif')
                        temp_gif.write(gif_bytes)
                        temp_gif.close()
                        
                        try:
                            await update.message.reply_animation(
                                animation=open(temp_gif.name, 'rb'),
                                caption='🔓 Расшифрованная GIF-анимация'
                            )
                            os.unlink(temp_gif.name)
                        except Exception as e:
                            logger.error(f"Ошибка при отправке анимации: {str(e)}")
                            await update.message.reply_document(
                                document=open(temp_gif.name, 'rb'),
                                filename="decrypted_animation.gif",
                                caption='🔓 Расшифрованная GIF-анимация (как файл)'
                            )
                            os.unlink(temp_gif.name)
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать GIF-анимацию.')
                else:
                    decoded = decode_text(encrypted_text)
                    if decoded:
                        await update.message.reply_text(f'🔓 Расшифрованное сообщение:\n{decoded}')
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать сообщение.')
            else:

                encoded = encode_text(text)
                

                full_message = f'🔒 Зашифрованное сообщение:\n{encoded}'
                if len(full_message) > MAX_MESSAGE_LENGTH:

                    await ask_for_split_confirmation(update, context, encoded)
                else:

                    await update.message.reply_text(full_message)
                    await update.message.reply_text(
                        '📋 <b>Как расшифровать сообщение:</b>\n'
                        '1. Отправьте это сообщение собеседнику\n'
                        '2. Собеседник должен переслать его боту для расшифровки',
                        parse_mode='HTML'
                    )
        else:

            encoded = encode_text(text)
            

            full_message = f'🔒 Зашифрованное сообщение:\n{encoded}'
            if len(full_message) > MAX_MESSAGE_LENGTH:

                await ask_for_split_confirmation(update, context, encoded)
            else:

                await update.message.reply_text(full_message)
                await update.message.reply_text(
                    '📋 <b>Как расшифровать сообщение:</b>\n'
                    '1. Отправьте это сообщение собеседнику\n'
                    '2. Собеседник должен переслать его боту для расшифровки',
                    parse_mode='HTML'
                )
    else:

        encoded = encode_text(text)
        

        full_message = f'🔒 Зашифрованное сообщение:\n{encoded}'
        if len(full_message) > MAX_MESSAGE_LENGTH:

            await ask_for_split_confirmation(update, context, encoded)
        else:

            await update.message.reply_text(full_message)
            await update.message.reply_text(
                '📋 <b>Как расшифровать сообщение:</b>\n'
                '1. Отправьте это сообщение собеседнику\n'
                '2. Собеседник должен переслать его боту для расшифровки',
                parse_mode='HTML'
            )


async def handle_animation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    

    animation = update.message.animation
    

    logger.info(f"Получена анимация: file_id={animation.file_id}, размер={animation.file_size}, тип={animation.mime_type}")
    
    # анимачки ниже 

    if "mp4" in animation.mime_type.lower() and not MOVIEPY_AVAILABLE:
        await update.message.reply_text(
            '❌ Для обработки MP4-анимаций требуется библиотека MoviePy.\n'
            'Установите её командой: `pip install moviepy`'
        )
        return
    
    try:

        animation_file = await context.bot.get_file(animation.file_id)
        logger.info(f"Успешно получена ссылка на файл: {animation_file.file_path}")
        

        status_message = await update.message.reply_text('🔄 Обрабатываю анимацию... Это может занять время (5 FPS, 50×50).')
        

        animation_bytes = await animation_file.download_as_bytearray()
        logger.info(f"Успешно скачан файл размером {len(animation_bytes)} байт")
        

        with open("temp_original_animation.gif", "wb") as f:
            f.write(animation_bytes)
        logger.info("Сохранен оригинальный файл для диагностики")
        

        is_mp4 = "mp4" in animation.mime_type.lower()
        

        encoded_result = None
        

        processed_bytes = resize_gif(animation_bytes, is_mp4=is_mp4)
        
        if processed_bytes:

            encoded_result = encode_image(processed_bytes, is_gif=True)
        
        if encoded_result:
            encoded_gif, file_path = encoded_result
            

            await status_message.edit_text('✅ Анимация успешно обработана!')
            

            await update.message.reply_text('⚠️ Внимание: файл может быть большим из-за высокого качества!')
            

            await update.message.reply_document(
                document=open(file_path, 'rb'),
                filename="encrypted_animation.txt",
                caption="🔒 Зашифрованная анимация (в файле)"
            )
            

            await update.message.reply_text(
                '📋 <b>Как использовать зашифрованную анимацию:</b>\n\n'
                '1️⃣ <b>Вариант 1 (файл):</b>\n'
                '   - Скачайте и перешлите этот файл боту\n\n'
                '2️⃣ <b>Вариант 2 (текст):</b>\n'
                '   - Откройте файл в текстовом редакторе\n'
                '   - Скопируйте всё содержимое\n'
                '   - Отправьте текст получателю\n'
                '   - Получатель пересылает это сообщение боту\n\n'
                '3️⃣ <b>Вариант 3 (если файл слишком большой):</b>\n'
                '   - Сообщение может быть разделено на части\n'
                '   - Отправьте все части боту по очереди\n'
                '   - Бот автоматически соберет и расшифрует сообщение',
                parse_mode='HTML'
            )
        else:
            await status_message.edit_text('❌ Не удалось обработать анимацию. Попробуйте отправить её как файл (GIF).')
    except Exception as e:
        logger.error(f"Ошибка при обработке анимации: {str(e)}", exc_info=True)
        await update.message.reply_text(f'❌ Произошла ошибка при обработке анимации: {str(e)}')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    

    is_waiting = USER_STATES.get(user_id, {}).get('waiting_for_photo', False)
    

    photo = update.message.photo[-1]
    

    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = await photo_file.download_as_bytearray()
    

    await update.message.reply_text('🔄 Обрабатываю изображение... Это может занять значительное время (PNG высокого качества).')
    

    try:
        encoded_result = encode_image(photo_bytes)
        
        if encoded_result:
            encoded_image, file_path = encoded_result
            

            await update.message.reply_text('⚠️ Внимание: файл может быть очень большим из-за высокого качества и отсутствия сжатия!')
            

            await update.message.reply_document(
                document=open(file_path, 'rb'),
                filename="encrypted_image_hq.txt",
                caption="🔒 Зашифрованное изображение высокого качества (в файле)"
            )
            

#конец анимачки 

            await update.message.reply_text(
                '📋 <b>Как использовать зашифрованное изображение:</b>\n\n'
                '1️⃣ <b>Вариант 1 (файл):</b>\n'
                '   - Скачайте и перешлите этот файл боту\n\n'
                '2️⃣ <b>Вариант 2 (текст):</b>\n'
                '   - Откройте файл в текстовом редакторе\n'
                '   - Скопируйте всё содержимое\n'
                '   - Отправьте текст получателю\n'
                '   - Получатель пересылает это сообщение боту\n\n'
                '3️⃣ <b>Вариант 3 (если файл слишком большой):</b>\n'
                '   - Сообщение может быть разделено на части\n'
                '   - Отправьте все части боту по очереди\n'
                '   - Бот автоматически соберет и расшифрует сообщение',
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text('❌ Не удалось зашифровать изображение.')
    except Exception as e:
        logger.error(f"Ошибка при шифровании изображения: {e}")
        await update.message.reply_text('❌ Произошла ошибка при шифровании изображения.')
    

    if user_id in USER_STATES:
        USER_STATES[user_id]['waiting_for_photo'] = False

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:


    document = update.message.document
    
    if document.mime_type in ["text/plain", "application/txt", "text/txt"] or document.file_name.endswith(".txt"):
        await update.message.reply_text('🔄 Обрабатываю файл...')
        

        doc_file = await context.bot.get_file(document.file_id)
        file_bytes = await doc_file.download_as_bytearray()
        

        try:
            file_text = file_bytes.decode('utf-8')
            

            if file_text.startswith(PREFIX) and (ZWSP in file_text or ZWNJ in file_text):

                if file_text.startswith(IMAGE_PREFIX):
                    await update.message.reply_text('🔄 Расшифровываю изображение высокого качества... Это может занять время.')

                    image_bytes = decode_image(file_text)
                    if image_bytes:

                        await update.message.reply_photo(
                            photo=io.BytesIO(image_bytes),
                            caption='🔓 Расшифрованное изображение высокого качества'
                        )
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать изображение из файла.')

                elif file_text.startswith(GIF_PREFIX):
                    await update.message.reply_text('🔄 Расшифровываю GIF-анимацию... Это может занять время.')

                    gif_bytes = decode_gif(file_text)
                    if gif_bytes:

                        temp_gif = tempfile.NamedTemporaryFile(delete=False, suffix='.gif')
                        temp_gif.write(gif_bytes)
                        temp_gif.close()
                        

                        try:
                            await update.message.reply_animation(
                                animation=open(temp_gif.name, 'rb'),
                                caption='🔓 Расшифрованная GIF-анимация'
                            )

                            os.unlink(temp_gif.name)
                        except Exception as e:
                            logger.error(f"Ошибка при отправке анимации: {str(e)}")

                            await update.message.reply_document(
                                document=open(temp_gif.name, 'rb'),
                                filename="decrypted_animation.gif",
                                caption='🔓 Расшифрованная GIF-анимация (как файл)'
                            )

                            os.unlink(temp_gif.name)
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать GIF-анимацию из файла.')
                else:

                    decoded = decode_text(file_text)
                    if decoded:
                        await update.message.reply_text(f'🔓 Расшифрованное сообщение:\n{decoded}')
                    else:
                        await update.message.reply_text('❌ Не удалось расшифровать сообщение из файла.')
            else:
                await update.message.reply_text('❌ Файл не содержит зашифрованных данных.')
        except UnicodeDecodeError:
            await update.message.reply_text('❌ Файл содержит не текстовые данные или неверная кодировка.')
    else:
        await update.message.reply_text('❌ Принимаются только текстовые файлы (.txt).')

def main() -> None:

    application = Application.builder().token("7633329337:AAGZxOp-DYPfLAnvsfdhntxexK0sIqXDNGM").build()


    application.add_handler(CommandHandler("start", start))
    

    application.add_handler(MessageHandler(filters.TEXT, handle_text))
    

    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    

    application.add_handler(MessageHandler(filters.ANIMATION, handle_animation))
    

    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    

    application.add_handler(CallbackQueryHandler(handle_split_callback))


    logger.info("🚀 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 
#конец типа тут хз чоо принт может а хз 