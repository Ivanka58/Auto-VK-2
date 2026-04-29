import vk_api
import os
import time

def send_to_vk_groups(token, group_ids, message_text, photo_paths):
    """
    Отправляет пост (текст + фото) в предложку/стену групп ВК от имени СООБЩЕСТВА.
    Требуется токен сообщества с правами: стена, фото, управление.
    """
    if not token or token == "":
        return "❌ Ключ ВК не подключен! Обратись к администратору @Ivanka58"

    # Простейшая проверка на "старый" пользовательский токен (необязательно, но полезно)
    if len(token) < 50:
        return ("⚠️ ВНИМАНИЕ: Твой токен слишком короткий и похож на старый пользовательский.\n"
                "Для работы через сообщество нужен токен, полученный в разделе 'Работа с API' "
                "вашего сообщества. Он длинный, начинается с 'vk1.a...'.\n"
                "Инструкция: https://vk.com/@yourgroup-api_access_token")

    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api()
        upload = vk_api.VkUpload(vk_session)

        # Загружаем фото на стену сообщества
        attachments = []
        if photo_paths:
            for path in photo_paths:
                if os.path.exists(path):
                    photo_upload = upload.photo_wall(path)[0]
                    attachments.append(f"photo{photo_upload['owner_id']}_{photo_upload['id']}")
                else:
                    print(f"Файл {path} не найден, пропускаем.")

        attachments_str = ",".join(attachments) if attachments else ""

        results = []
        for gid in group_ids:
            try:
                # Публикуем пост на стене группы (от имени сообщества)
                vk.wall.post(
                    owner_id=gid,
                    message=message_text,
                    attachments=attachments_str,
                    signed=False      # Пост от имени сообщества, без подписи пользователя
                )
                results.append(f"✅ Группа {gid}: объявление опубликовано (или отправлено на модерацию).")
            except vk_api.exceptions.ApiError as e:
                err = str(e)
                if "access_denied" in err or "15" in err:
                    results.append(f"❌ Группа {gid}: доступ запрещён. Возможно, отключена предложка или ваш паблик забанен.")
                elif "5" in err:
                    results.append(f"⚠️ Группа {gid}: требуется подтверждение (капча). Действие не выполнено.")
                else:
                    results.append(f"❌ Группа {gid}: ошибка ВК — {err[:100]}")
            except Exception as e:
                results.append(f"❌ Группа {gid}: ошибка — {str(e)[:100]}")

            time.sleep(0.5)   # Защита от флуда

        return "\n".join(results)

    except Exception as e:
        return f"🔥 Критическая ошибка ВК: {e}. Обратись к @Ivanka58"
