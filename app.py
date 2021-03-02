from flask import Flask, render_template, url_for, request
from flask_sqlalchemy import SQLAlchemy
import pickle
import joblib
import numpy as np
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    userpass =db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return '<Task %r>' % self.id

##print the rest here
class popularity_recommender_py():
    def __init__(self):
        self.train_data = None
        self.user_id = None
        self.item_id = None
        self.popularity_recommendations = None
        
    #Create the popularity based recommender system model
    def create(self, train_data, user_id, item_id):
        self.train_data = train_data
        self.user_id = user_id
        self.item_id = item_id
 
        #Get a count of user_ids for each unique song as recommendation score
        train_data_grouped = train_data.groupby([self.item_id]).agg({self.user_id: 'count'}).reset_index()
        train_data_grouped.rename(columns = {'user_id': 'score'},inplace=True)
    
        #Sort the songs based upon recommendation score
        train_data_sort = train_data_grouped.sort_values(['score', self.item_id], ascending = [0,1])
    
        #Generate a recommendation rank based upon score
        train_data_sort['Rank'] = train_data_sort['score'].rank(ascending=0, method='first')
        
        #Get the top 10 recommendations
        self.popularity_recommendations = train_data_sort.head(10)
 
    #Use the popularity based recommender system model to
    #make recommendations
    def recommend(self, user_id):    
        user_recommendations = self.popularity_recommendations
        
        #Add user_id column for which the recommendations are being generated
        user_recommendations['user_id'] = user_id
    
        #Bring user_id column to the front
        cols = user_recommendations.columns.tolist()
        cols = cols[-1:] + cols[:-1]
        user_recommendations = user_recommendations[cols]
        return user_recommendations

class item_similarity_recommender_py():
    def __init__(self):
        self.train_data = None
        self.user_id = None
        self.item_id = None
        self.cooccurence_matrix = None
        self.songs_dict = None
        self.rev_songs_dict = None
        self.item_similarity_recommendations = None
        
    #Get unique items (songs) corresponding to a given user
    def get_user_items(self, user):
        
        user_data = self.train_data[self.train_data[self.user_id] == user]
        return list(user_data[self.item_id].unique())
        
    #Get unique users for a given item (song) 
    # nep: user le suneko item(geet) haru suneka unique users
    def get_item_users(self, item):
        item_data = self.train_data[self.train_data[self.item_id] == item]
        item_users = set(item_data[self.user_id].unique())
            
        return item_users # user le suneko geet ko unique listeners haru ko set
        
    #Get unique items (songs) in the training data
    #nep: sabai items (geet) haru
    def get_all_items_train_data(self):
        return list(self.train_data[self.item_id].unique())

        #aba hami sange k k cha: user le suneko geet ko aru users ani all songs
        
    #Construct cooccurence matrix
    def construct_cooccurence_matrix(self, user_songs, all_songs):
            
        ####################################
        #Get users for all songs in user_songs.
        ####################################
        user_songs_users = [
            self.get_item_users(user_songs[i]) for i in range(len(user_songs))
        ]

        ###############################################
        #Initialize the item cooccurence matrix of size 
        #len(user_songs) X len(songs)
        ###############################################
        cooccurence_matrix = np.matrix(np.zeros(shape=(len(user_songs), len(all_songs))), float)

        #############################################################
        #Calculate similarity between user songs and all unique songs
        #in the training data
        #############################################################
        for i in range(len(all_songs)):
            #Calculate unique listeners (users) of song (item) i
            songs_i_data = self.train_data[self.train_data[self.item_id] == all_songs[i]]
            users_i = set(songs_i_data[self.user_id].unique())

            for j in range(len(user_songs)):       

                #Get unique listeners (users) of song (item) j
                users_j = user_songs_users[j]

                #Calculate intersection of listeners of songs i and j
                users_intersection = users_i.intersection(users_j)

                #Calculate cooccurence_matrix[i,j] as Jaccard Index
                if len(users_intersection) != 0:
                    #Calculate union of listeners of songs i and j
                    users_union = users_i.union(users_j)

                    cooccurence_matrix[j,i] = float(len(users_intersection))/float(len(users_union))
                else:
                    cooccurence_matrix[j,i] = 0


        return cooccurence_matrix
 
    
    #Use the cooccurence matrix to make top recommendations
    def generate_top_recommendations(self, user, cooccurence_matrix, all_songs, user_songs):
        print("Non zero values in cooccurence_matrix :%d" % np.count_nonzero(cooccurence_matrix))

        #Calculate a weighted average of the scores in cooccurence matrix for all user songs.
        user_sim_scores = cooccurence_matrix.sum(axis=0)/float(cooccurence_matrix.shape[0])
        user_sim_scores = np.array(user_sim_scores)[0].tolist()

        #Sort the indices of user_sim_scores based upon their value
        #Also maintain the corresponding score
        sort_index = sorted(((e,i) for i,e in enumerate(list(user_sim_scores))), reverse=True)

        #Create a dataframe from the following
        columns = ['user_id', 'song', 'score', 'rank']
        #index = np.arange(1) # array of numbers for the number of samples
        df = pd.DataFrame(columns=columns)

        #Fill the dataframe with top 10 item based recommendations
        rank = 1
        for i in range(len(sort_index)):
            if ~np.isnan(sort_index[i][0]) and all_songs[sort_index[i][1]] not in user_songs and rank <= 10:
                df.loc[len(df)]=[user,all_songs[sort_index[i][1]],sort_index[i][0],rank]
                rank += 1

        #Handle the case where there are no recommendations
        if df.shape[0] != 0:
            return df

        print("The current user has no songs for training the item similarity based recommendation model.")
        return -1
 
    #Create the item similarity based recommender system model
    def create(self, train_data, user_id, item_id):
        self.train_data = train_data
        self.user_id = user_id
        self.item_id = item_id
 
    #Use the item similarity based recommender system model to
    #make recommendations
    def recommend(self, user):
        
        ########################################
        #A. Get all unique songs for this user
        ########################################
        user_songs = self.get_user_items(user)    
            
        print("No. of unique songs for the user: %d" % len(user_songs))
        
        ######################################################
        #B. Get all unique items (songs) in the training data
        ######################################################
        all_songs = self.get_all_items_train_data()
        
        print("no. of unique songs in the training set: %d" % len(all_songs))
         
        ###############################################
        #C. Construct item cooccurence matrix of size 
        #len(user_songs) X len(songs)
        ###############################################
        cooccurence_matrix = self.construct_cooccurence_matrix(user_songs, all_songs)
        
        #######################################################
        #D. Use the cooccurence matrix to make recommendations
        #######################################################
        df_recommendations = self.generate_top_recommendations(user, cooccurence_matrix, all_songs, user_songs)
                
        return df_recommendations
    
    #Get similar items to given items
    def get_similar_items(self, item_list):
        
        user_songs = item_list

        ######################################################
        #B. Get all unique items (songs) in the training data
        ######################################################
        all_songs = self.get_all_items_train_data()

        print("no. of unique songs in the training set: %d" % len(all_songs))

        ###############################################
        #C. Construct item cooccurence matrix of size 
        #len(user_songs) X len(songs)
        ###############################################
        cooccurence_matrix = self.construct_cooccurence_matrix(user_songs, all_songs)

        #######################################################
        #D. Use the cooccurence matrix to make recommendations
        #######################################################
        user = ""
        return self.generate_top_recommendations(
            user, cooccurence_matrix, all_songs, user_songs
        )

popularity = joblib.load('model_pickle')
collaborative = joblib.load('collaborative_recommend')



print(popularity.recommend('userid'))


#@app.route('/')
#def index():
#    return render_template('index.html', output = classi.recommend('useridindf'))

@app.route('/')
def index():
    #user_id = [string(x) for x in request.form.values()]
    return render_template('popularity.html')##, output2 = collaborative.get_similar_items(['Use Somebody _ Kings Of Leon']))


@app.route('/popular', methods=['POST','GET'])
def hello():
    if request.method != 'POST':
        return render_template('index.html')

    userid = request.form["userid"]
    outt = popularity.recommend(userid)
    return render_template('popularity.html', output2 = outt)


@app.route('/basedonyou', methods=['POST','GET'])
def basedonyou():
    if request.method != 'POST':
        return render_template('index.html')

    song1 = request.form["song1"]
    song2 = request.form["song2"]
    song3 = request.form["song3"]
    song4 = request.form["song4"]
    song5 = request.form["song5"]
    outt = collaborative.get_similar_items([song1, song2, song3, song4, song5])
    return render_template('popularity.html', output2 = outt)

@app.route('/similarsongs', methods=['POST','GET'])
def similarsongs():
    if request.method != 'POST':
        return render_template('index.html')

    song_based = request.form["song"]
    outt = collaborative.get_similar_items([song_based])
    return render_template('popularity.html', output2 = outt)

if __name__  =="__main__":
    app.run(debug=True)