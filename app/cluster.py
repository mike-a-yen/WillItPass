import numpy as np

#import matplotlib
#matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import mpld3
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns

def plot_3d(xy, clusters):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(xy[:,0],xy[:,1],xy[:,2],
               c=clusters,
               cmap='jet',
               alpha=0.2,
               edgecolors='none')
    
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.set_zticklabels([])
    plt.axis('off')
    return mpld3.fig_to_html(fig)
    
def plot_2d(xy, clusters, votes):
    fig = plt.figure(figsize=(6,4))
    ax = fig.add_subplot(111)

    ax.scatter(xy[:,0]+xy[:,2],
               xy[:,1]-xy[:,2],
               c=clusters,
               s=50*votes+20,
               cmap='jet',
               alpha=0.2,
               edgecolors='none')
    
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.tick_params(axis=u'both', which=u'both',length=0)
    plt.axis('off')
    html = mpld3.fig_to_html(fig)
    fig_file = open('app/static/img/cluster.html','w')
    fig_file.write(html)
    fig_file.close()
    return 'app/static/img/cluster.html'
    
