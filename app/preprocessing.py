import pandas as pd
import re
import pickle
from app.utils import document_title
from sklearn.feature_extraction.text import TfidfVectorizer

from sklearn.decomposition import TruncatedSVD
from sklearn.cluster import DBSCAN, KMeans
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

def cluster_tfidf(tfidf_matrix, projection):
    svd = TruncatedSVD(n_components=1000)
    normalizer = Normalizer(copy=False)
    lsa = make_pipeline(svd, normalizer)

    coords = lsa.fit_transform(tfidf_matrix)
    explained_variance = svd.explained_variance_ratio_.sum()
    print("Explained variance of the SVD step: {}%".format(
         int(explained_variance * 100)))

    model = KMeans(12)
    clusters = model.fit_predict(coords)

    reduc = TruncatedSVD(n_components=projection)
    xy = reduc.fit_transform(coords)

    return xy, clusters

#raw = pd.read_csv('data/boxer.csv')
#raw['bill_title'] = raw['bill'].apply(document_title)
#raw['amendment_title'] = raw['amendment'].apply(document_title)
#raw['text'] = raw['question'].str.cat(raw['bill_title'],sep=' ')
#raw['text'] = raw['text'].str.cat(raw['amendment_title'],sep=' ')
#raw['text'] = raw['text'].apply(lambda x: re.sub("\d+", "", x))

raw = pd.read_csv('data/app_data.csv')
votes = raw['vote'].values

#tfidf = TfidfVectorizer(max_df=0.5,min_df=2,
#                        max_features=10000,
#                        stop_words='english',
#                        use_idf=True, tokenizer=None, ngram_range=(1,3))
#tfidf_matrix = tfidf.fit_transform(raw['text'])
tfidf_matrix = pickle.load(open('data/tfidf_matrix.pklb','rb'))

#xy, clusters = cluster_tfidf(tfidf_matrix, 3)
#pickle.dump(xy,
#            open('data/xy.pklb','wb'))
#pickle.dump(clusters,
#            open('data/clusters.pklb','wb'))

xy = pickle.load(open('data/xy.pklb','rb'))
clusters = pickle.load(open('data/clusters.pklb','rb'))
