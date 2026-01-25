import vk_api
import os

def send_to_vk_groups(token, group_ids, message_text, photo_paths):
    if not token or token == "":
        return "Ключ вк не подключен!! Обратись к администратору @Ivanka58"

    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api()
        upload = vk_api.VkUpload(vk_session)

        # Загружаем все фотографии и собираем их ID в список
        attachments = []
        for path in photo_paths:
            photo_upload = upload.photo_wall(path)[0]
            attachments.append(f"photo{photo_upload['owner_id']}_{photo_upload['id']}")

        # Превращаем список в строку через запятую для ВК
        attachments_str = ",".join(attachments)

        results = []
        for gid in group_ids:
            try:
                # Отправка поста в предложку
                vk.wall.post(owner_id=gid, message=message_text, attachments=attachments_str)
                results.append(f"Группа {gid}: Отправлено ✅")
            except:
                results.append(f"Группа {gid}: Ошибка, группа закрыта, обратись к администратору @Ivanka58")
        
        return "\n".join(results)

    except Exception as e:
        return f"Критическая ошибка ВК: {e}. Обратись к @Ivanka58"
