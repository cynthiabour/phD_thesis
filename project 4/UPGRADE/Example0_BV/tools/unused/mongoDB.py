# from dotenv import load_dotenv, find_dotenv
import os
import pprint
from pymongo import MongoClient

# load_dotenv(find_dotenv())


password = os.environ.get("MONGODB_PWD")

connection_string = f"mongodb+srv://cynthiabour:mpikgchemistry2022@cluster0.glr1fvv.mongodb.net/?retryWrites=true&w=majority"

client = MongoClient(connection_string)
print(client)
# name of all Librarian
dbs = client.list_database_names()
BV_db = client.BV
collections = BV_db.list_collection_names()

def insert_test_doc():
    #insert a document
    collection = BV_db.BV_1
    test_document = {
        "name": "wei-hsin",
        "type": "Test"
    }
    inserted_id = collection.insert_one(test_document).inserted_id
    print(inserted_id)

def find_test_doc():
    pprint.pprint(BV_db.BV_1.find_one())

def main():
    find_test_doc()



if __name__ == "__main__":
    main()