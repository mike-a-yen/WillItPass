from app import BASE_DIR

from app import db
from app.models import *
from app.member_utils import (member_vote_table,
                              member_vote_subject_table,
                              get_bill_top_subject,
                              vote_map)
from app.utils import (get_member)

import os
import pandas as pd
import numpy as np
import re
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count
from functools import partial

from sklearn import base
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline,FeatureUnion
from sklearn.preprocessing import StandardScaler, Normalizer, LabelBinarizer, OneHotEncoder
from sklearn.externals import joblib
from sklearn.exceptions import DataConversionWarning

import warnings
warnings.simplefilter('ignore',category=DataConversionWarning)
warnings.simplefilter('ignore',category=UserWarning)

import nltk
nltk.data.path.append(BASE_DIR+'/nltk_data/')
from nltk.stem.snowball import SnowballStemmer
from textblob import TextBlob
stemmer = SnowballStemmer('english')

stopwords = nltk.corpus.stopwords.words('english')
stopwords += ['amdt', 'amend', 'amendment',
              'bill', 'motion','title','act','samdt',
              'table','year','cba','pn','con','sec',
              'fy','use','used','uses','federal','government',
              'america','conduct','code','alan','purposes',
              'commission','commitee','senate']


def tokenize_and_stem(text, stopwords=stopwords):
    tokens = [word for word in TextBlob(text).words]
    filtered_tokens = [re.sub('[^a-zA-Z]','',w) for w in tokens]
    stems = [stemmer.stem(t) for t in filtered_tokens]
    return stems

title_vectorizer = TfidfVectorizer(max_features=200,
                                   ngram_range=(1,2),
                                   max_df = 0.95,
                                   min_df = 0.01,
                                   tokenizer=tokenize_and_stem,
                                   stop_words=stopwords)

text_vectorizer = TfidfVectorizer(max_features=1000,
                                  ngram_range=(1,3),
                                  max_df = 0.95,
                                  min_df = 0.01,
                                  tokenizer=tokenize_and_stem,
                                  stop_words=stopwords)

class FeatureSelector(base.BaseEstimator,base.TransformerMixin):
    def __init__(self,key):
        self.key = key

    def fit(self, x,y=None):
        return self

    def transform(self,data_dict,y=None):
        return data_dict[self.key]

class SubjectEncoder(base.BaseEstimator,base.TransformerMixin):
    def fit(self,X,y=None):
        return self

    def transform(self,X):
        return [{subject:1} for subject in X]


class DateEncoder(base.BaseEstimator,base.TransformerMixin):
    def fit(self,X,y=None):
        return self

    def transform(self,X):
        return X.apply(datetime.timestamp).values[:,np.newaxis]
    

class DataPipeline(FeatureUnion):
    def __init__(self,**kwargs):
        self.title_features = Pipeline([('selector',FeatureSelector('title')),
                                        ('tfidf',title_vectorizer),
                                        ('scale',Normalizer())])
        self.top_subject_features = Pipeline([('selector',FeatureSelector('top_subject')),
                                              ('encoder',LabelBinarizer(sparse_output=True))])
        self.date_features = Pipeline([('selector',FeatureSelector('date')),
                                       ('encoder',DateEncoder())])
        self.text_features = Pipeline([('selector',FeatureSelector('text')),
                                       ('tfidf',text_vectorizer),
                                       ('scale',Normalizer())])
        
        FeatureUnion.__init__(self,
                              transformer_list=[('title',self.title_features),
                                                ('top_subject',self.top_subject_features),
                                                ('date',self.date_features),
						('text',self.text_features)],
				**kwargs)

def accuracy(actual,prediction):
    return np.mean(actual==prediction)


def mean_binary_accuracy(estimator,X,y):
    predictions = estimator.predict(X)
    return accuracy(y,predictions)


def train_model(X,y):
    data_pipeline = DataPipeline()
    X = data_pipeline.fit_transform(X)

    clf = KNeighborsClassifier()
    k_range = {'n_neighbors':[1,5,10,50,100]}
    weights =  {'weights':['uniform','distance'],
                'p':[1,2]}
    
    for param in [k_range,weights]:
        search = GridSearchCV(clf,
                              param_grid=param,
                              scoring=mean_binary_accuracy)
        search.fit(X,y)
        clf = search.best_estimator_
        print(param.keys(),search.best_params_,search.best_score_)

    model = Pipeline([('transform',data_pipeline),
                     ('model',clf)])
    best_accuracy = search.best_score_
    return model, best_accuracy


def build_model(memid):
    """Build a knn model for each member
    member is a database Member object
    """
    df = member_vote_table(memid)
    df.dropna(subset=['vote'],inplace=True)
    df.fillna('',inplace=True)
    y = df['vote']
    X = df.drop(['vote'],axis=1)

    if len(X) < 10: # new member
        model = None
        data_transformer = None
        accuracy = np.nan
    else:
        model,accuracy = train_model(X,y)
        data_transformer = model.steps[0][1]
    return model, accuracy, data_transformer


def populate_model(proposed_db_model):
    memid = proposed_db_model.member_id
    version = proposed_db_model.version
    query = db.session.query(PredictionModel)\
                      .filter_by(member_id=proposed_db_model.member_id)\
                      .filter_by(version=version).first()
    if query:
        query.algorithm = proposed_db_model.algorithm
        query.accuracy = proposed_db_model.accuracy
        query.date = datetime.now()
        db.session.commit()
    else:
        db.session.add(proposed_db_model)
        db.session.commit()
    

def build_save_model(member,version):
    memid = member.member_id
    print(member.first_name,member.last_name,member.member_id)
    if not os.path.exists('data/nn_models/v%s'%version):
        os.mkdir('data/nn_models/v%s'%version)
    if not os.path.exists('data/pipelines/v%s'%version):
        os.mkdir('data/pipelines/v%s'%version)

    pipeline_path = os.path.join(BASE_DIR,'data',
                                 'pipelines','v%s'%version,
                                 '%s.pklb'%memid)
    model_path = os.path.join(BASE_DIR,'data',
                              'nn_models','v%s'%version,
                              '%s.pklb'%memid)

    print(member.display_name,member.member_id)
    model, accuracy, transformer = build_model(memid)
    print(member.display_name,member.member_id,accuracy)
    algorithm = re.search('([a-zA-Z0-9]+)',model.steps[1][1].__repr__()).group()
    db_model = PredictionModel(memid,
                               model_path,
                               pipeline_path,
                               algorithm,
                               version,
                               accuracy,
                               datetime.now())
    populate_model(db_model)
    pipeline_file = open(pipeline_path,'wb')
    model_file = open(model_path,'wb')
    joblib.dump(transformer,pipeline_file)
    joblib.dump(model,model_file)
    return True
    
def build_models(version,members=None):
    """Build knn models for all members in DB
    this can be run whenever the db gets an update
    """
    if members == None:
        members = db.session.query(Member).all()
    results = [build_save_model(member,version) for member in members]
    return np.mean(results) == 1
    
def get_subject_votes(memid):    
    df = pd.DataFrame(list(zip(subjects,votes)), columns=['subject','vote'])
    return df

def rank_subjects(memid):
    df = member_vote_subject_table(memid)
    df = df[df['vote'].isin(['Nay','Yea'])]
    df['value'] = df['vote'].apply(vote_map)
    group = df.groupby(['subject'],as_index=False)
    agg = group.agg(['mean','count'])['value']\
               .sort_values(['mean','count'],ascending=False)
    agg['for_vote'] = (agg['mean']*agg['count']).astype(int)
    agg['against_vote'] = agg['count']-agg['for_vote']
    agg = agg.round({'mean':2})
    return agg.reset_index(0)

def positive_negative_subjects(memid,wiggle_room=0.5,limit=5):
    ranked = rank_subjects(memid)
    positive = ranked[ranked['mean']>=1-wiggle_room].sort_values(['mean','for_vote'],ascending=False)
    negative = ranked[ranked['mean']<=wiggle_room].sort_values(['mean','against_vote'],ascending=[True,False])
    positive_counts = positive[['subject','for_vote','count']].iloc[0:limit]
    positive_counts.columns=['subject','for_votes','total_votes']
    negative_counts = negative[['subject','against_vote','count']].iloc[0:limit]
    negative_counts.columns=['subject','against_votes','total_votes']
    return (positive_counts.T.to_dict().values(),
            negative_counts.T.to_dict().values())

def voting_subject_record(memid):
    ranked = rank_subjects(memid)
    return ranked.T.to_dict().values()


if __name__ == '__main__':
    latest_version = db.session.query(PredictionModel.version)\
                               .order_by(PredictionModel.version.desc()).first()
    build_models(latest_version)
