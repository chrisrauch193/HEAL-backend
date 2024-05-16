# src/database/message_op.py
from peewee import DoesNotExist
from datetime import datetime

from .data_models import MedicalTerm, MedicalTermTranslation, Message, MessageTermCache, MedicalTermSynonym, MessageTranslationCache

def get_chat_messages(room_id: int, page_num: int, limit_num: int, language_code: str) -> dict:
    offset = (page_num - 1) * limit_num
    room_messages = Message.select().where(Message.room == room_id).order_by(Message.id).limit(limit_num).offset(offset)
    room_message_list = []

    for room_message in room_messages:
        room_message_list.append(get_message(room_id, room_message.id, language_code))

    return room_message_list

def get_message(room_id: int, message_id: int, language_code: str) -> dict:
    message = Message.get((Message.room == room_id) & (Message.id == message_id))

    try:
        translation = MessageTranslationCache.get((MessageTranslationCache.message == message_id) & (MessageTranslationCache.language_code == language_code))
        translated_text = translation.translated_text
    except DoesNotExist:
        translated_text = message.text

    terms = MessageTermCache.select().where(MessageTermCache.message == message_id)
    medical_terms = [
        {
            'id': term.medical_term.id,
            'synonym': term.translated_synonym.synonym if term.translated_synonym else term.original_synonym.synonym,
            'termInfo': get_term(term.medical_term.id, language_code)
        } for term in terms
    ]

    ret = {
        "messageId": message.id,
        "roomId": message.room.id,
        "senderUserId": message.user.id,
        "timestamp": message.send_time,
        "content": {
            "text": message.text,
            "metadata": {
                "translation": translated_text,
                "medicalTerms": medical_terms
            }
        }
    }

    return ret


def create_term(term_info):
    new_term = MedicalTerm.create(term_type=term_info.get('term_type', 'GENERAL'))
    new_term.save()

    new_translation = MedicalTermTranslation.create(
        medical_term=new_term.id,
        language_code=term_info.get('language_code', 'en'),
        name=term_info.get('name'),
        description=term_info.get('description'),
        url=term_info.get('url')
    )
    new_translation.save()

    for synonym in term_info.get('synonyms', []):
        MedicalTermSynonym.create(
            medical_term=new_term.id,
            synonym=synonym.get('synonym'),
            language_code=synonym.get('language_code', 'en')
        )

    return new_term.id

def get_term(term_id, language_code):
    medical_term = MedicalTerm.get(MedicalTerm.id == term_id)
    translation = MedicalTermTranslation.get(
        (MedicalTermTranslation.medical_term == term_id) & 
        (MedicalTermTranslation.language_code == language_code)
    )

    ret = {
        "medicalTermId": term_id,
        "medicalTermType": medical_term.term_type,
        "name": translation.name,
        "description": translation.description,
        "medicalTermLinks": [
            translation.url
        ]
    }

    return ret

def get_terms_all(language_code: str):
    medical_terms = MedicalTerm.select()
    term_list = []

    for medical_term in medical_terms:
        term_id = medical_term.id
        term_info = get_term(term_id, language_code)
        term_list.append(term_info)

    ret = {
        "medicalTerms": term_list
    }

    return ret

def update_term(term_id: int, term_update_info: dict):
    term = MedicalTerm.get(MedicalTerm.id == term_id)
    translation = MedicalTermTranslation.get(MedicalTermTranslation.medical_term == term_id)

    if 'term_type' in term_update_info:
        term.term_type = term_update_info.get('term_type')

    if 'language_code' in term_update_info:
        translation.language_code = term_update_info.get('language_code')

    if 'description' in term_update_info:
        translation.description = term_update_info.get('description')

    if 'url' in term_update_info:
        translation.url = term_update_info.get('url')

    term.save()
    translation.save()
    return term

def delete_term(term_id: int):
    term = MedicalTerm.get(MedicalTerm.id == term_id)
    term.delete_instance()
    return

def create_link(message_id, term_id, original_synonym_id=None, translated_synonym_id=None):
    new_cache = MessageTermCache.create(
        medical_term=term_id,
        message=message_id,
        original_synonym=original_synonym_id,
        translated_synonym=translated_synonym_id
    )
    new_cache.save()

    message = Message.get(Message.id == message_id)
    term_info = get_term(term_id, message.language_code)
    terms_info_in_cache = get_message_terms(message_id, message.language_code)

    ret = {
        "message": {
            "messageId": message_id,
            "senderUserId": message.user.id,
            "sendTime": message.send_time,
            "message": message.text,
            "medicalTerms": terms_info_in_cache
        },
        "MedicalTerm": term_info
    }

    return ret

def get_message_terms(message_id, language_code):
    message_term_cache = MessageTermCache.select().where(MessageTermCache.message == message_id)
    terms_list = []

    for cache in message_term_cache:
        term_id_in_cache = cache.medical_term.id
        term = get_term(term_id_in_cache, language_code)
        terms_list.append(term)

    return terms_list

# TODO: THis is just a template. Please get the right information and put it in
def search_medical_terms(query):
    # Search for the term directly or by synonyms
    medical_terms = MedicalTerm.select().join(MedicalTermSynonym).where(
        (MedicalTerm.term_type.contains(query)) |
        (MedicalTermSynonym.synonym.contains(query))
    )

    results = []
    for term in medical_terms:
        term_translations = MedicalTermTranslation.select().where(MedicalTermTranslation.medical_term == term.id)
        translations = [{
            "language": trans.language_code,
            "default_name": trans.name,
            "description": trans.description,
            "url": trans.url
        } for trans in term_translations]

        synonyms = MedicalTermSynonym.select().where(MedicalTermSynonym.medical_term == term.id)
        synonym_list = [{
            "synonym": synonym.synonym,
            "language": synonym.language_code
        } for synonym in synonyms]

        results.append({
            "term_id": term.id,
            "medical_term_type": term.term_type,
            "translations": translations,
            "synonyms": synonym_list
        })

    return results

# TODO: THis is just a template. Please get the right information and put it in
def save_message(roomId, userId, original_text, translated_text, medical_terms, translated_medical_terms):
    message = Message.create(
        User_id=userId,
        Room_id=roomId,
        Text=original_text,
        Send_time=datetime.now()
    )
    message.save()
    
    MessageTranslationCache.create(
        Message_id=message.id,
        Language_code=user_language,
        Translated_text=translated_text
    ).save()

    for term in medical_terms:
        MessageTermCache.create(
            Message_id=message.id,
            MedicalTerm_id=term['id'],
            Original_language_synonym=term['synonym'],
            Translated_language_synonym=None
        ).save()

    for term in translated_medical_terms:
        cache = MessageTermCache.get(
            MessageTermCache.Message_id == message.id,
            MessageTermCache.MedicalTerm_id == term['id']
        )
        cache.Translated_language_synonym = term['synonym']
        cache.save()

    return message
