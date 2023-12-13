import pandas as pd
import numpy as np


class Scores(object):
    
    def __init__(self, data):
        self.scores = pd.DataFrame.from_dict(data)
        try:
            self.scores.sort_values('minute', inplace=True)
            self.scores['cumulative'] = self.scores.value.cumsum() 
        
            self.total = self.scores['cumulative'].iloc[-1]
        except:
            self.total = 0

    def in_times(self, time_range):
        on_field = []
        for i, score in self.scores.iterrows():
            for trange in time_range:
                on_field.append(trange[0] <= score.minute <= trange[1])
        return self.scores[on_field]
    
            
    def count(self, score_type="try"):
        """Count the number of a given type of scoring event."""
        df = self.scores
        try:
            return df[df['type']==score_type].count()['value']
        except KeyError:
            return 0
            
    def to_dict(self):
        """Represent scores as a dictionary."""
        data = []
        for i, row in self.scores[['player', 'type', 'value', 'minute']].iterrows():
            data.append(row.to_dict())
        return data

    def __repr__(self):
        out = []
        for key, value in self.scores.iterrows():
            out.append("{b[player]}\t{b[type]}".format(b=value))
        return ("\n").join(out) #, "\n")
    
    @property
    def html(self):
        out = []
        for key, value in self.scores.iterrows():
            out.append("<tr><td>{b[minute]}</td><td>{b[player]}</td><td>{b[type]}</td><td>{b[cumulative]}</td></tr>".format(a=key, b=value))
        return "<table>" + ("\n").join(out) + "</table>" #, "\n")
    
    def _repr_html_(self):
        return self.html
