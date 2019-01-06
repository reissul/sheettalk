import argparse
import datetime
from sqlalchemy import Column, ForeignKey, Integer, String#, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
 
Base = declarative_base()

class User(Base):
    __tablename__ = 'User'
    id = Column(Integer, primary_key=True)
    number = Column(String(250))

class Spreadsheet(Base):
    __tablename__ = 'Spreadsheet'
    id = Column(Integer, primary_key=True)
    spreadsheet_google_id = Column(String(250))
    user_id = Column(Integer, ForeignKey('User.id'))
    user = relationship(User)

#class ActiveSpreadsheet(Base):
#    __tablename__ = 'ActiveSpreadsheet'
#    id = Column(Integer, primary_key=True)
#    user_id = Column(Integer, ForeignKey('User.id'))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='.')
    parser.add_argument("--db", help="Db name.", default="sheettalk")
    args = parser.parse_args()

    # Create engine and tables.
    engine = create_engine('sqlite:///{}.db'.format(args.db))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
