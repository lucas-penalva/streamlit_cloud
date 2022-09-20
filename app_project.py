import pandas as pd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
import geopandas
import streamlit as st
import plotly.express as px
from datetime import datetime

st.set_page_config(layout = 'wide')

@st.cache( allow_output_mutation=True)
def get_data(path):  
    data = pd.read_csv(path)

    return data

@st.cache( allow_output_mutation=True )
def get_geofile( url ):
    geofile = geopandas.read_file( url )

    return geofile

def clean_data(data):
    # transformando o atributo date
    data['date'] = pd.to_datetime(data['date'], format='%Y-%m-%d' )
    # erro de digitação
    data = data.drop(data[data['bedrooms'] == 33].index)

    return data

def set_feature ( data ):
    # add new features
    data['date'] = pd.to_datetime(data['date'], format='%Y-%m-%d' )    

    data['porao'] = data['sqft_basement'].apply(lambda x: 'com_porao' if x > 0 else 'sem_porao')

    data['year_over_year'] = data['date'].dt.strftime('%Y')    

    data['renovated'] = data['yr_renovated'].apply(lambda x: 'no' if x == 0 else 'yes')

    data['describe_condition'] = data['condition'].apply(lambda x: 'too bad' if x == 1 else
                                                         'bad' if x == 2 else
                                                         'median'if x == 3 else
                                                         'good' if x == 4 else
                                                         'excellent')
    # separando os meses para coletar cada estação do ano
    data['month'] = data.date.dt.month

    data['year'] = data['yr_built'].apply(lambda x: '< 1955' if x < 1955 else '> 1955')

    # criação de uma nova feature, indicando as estações do ano
    data['season'] = data['month'].apply(lambda x: 'Summer' if 6 <= x <= 8 else 'Fall' if 9 <= x <= 11 else 'Winter' if (x == 12) or (x == 1) or (x == 2) else 'Spring' if 3 <= x <= 5 else None)                                                             

    return data

def overview_data( data ):

    st.title('Propriedades para compra')
    st.sidebar.title('HR Project')

    st.write('Este app foi desenvolvido para mostrar uma tabela com todos os imóveis sugeridos para a House Rocket comprar.')
    st.write('Selecione os filtros no menu esquerdo para melhor visualização.')

    f_condition = st.sidebar.multiselect('Select condition', data.describe_condition.unique())
    f_zipcode = st.sidebar.multiselect('Enter zipcode', data.zipcode.unique())      
    
    # Agrupar os imóveis por região ( zipcode ). Encontrar a mediana do preço do imóvel.
    df1 = data[['zipcode', 'price']].groupby('zipcode').median().reset_index()
    df1 = df1.rename(columns={'price': 'price_median'})

    data = pd.merge(df1, data, on='zipcode', how='inner')

    # status
    for i in range(len(data)):
        if (data.loc[i, 'price'] < data.loc[i, 'price_median']) & (data.loc[i, 'condition'] >=3):
            data.loc[i, 'status'] = 'buy'
        else:
            data.loc[i, 'status'] = 'not buy'

    # Seleção dos imóveis
    buy_houses = data[data['status'] == 'buy'].sort_values(by=['describe_condition','price']).reset_index()         

    if (f_zipcode == []) & (f_condition != []):
        buy_houses = buy_houses.loc[buy_houses['describe_condition'].isin(f_condition), :]
    else: 
        pass

    if (f_zipcode != []) & (f_condition != []):
        buy_houses = buy_houses.loc[(buy_houses['zipcode'].isin(f_zipcode)) & (buy_houses['describe_condition'].isin(f_condition)), :]
    else:
        pass

    if (f_zipcode != []) & (f_condition == []):
        buy_houses = buy_houses.loc[data['zipcode'].isin(f_zipcode), :] 
    else:
        pass       

    st.dataframe(buy_houses[['id','zipcode', 'price', 'price_median', 'describe_condition', 'status']])  
    st.write('Foram encontrados {} imóveis sugeridos para compra dentro das condições filtradas'.format(len(buy_houses))) 

    if st.checkbox('Show Maps'):

        houses = buy_houses[['id','lat','long','price','zipcode']]
        # draw map
        fig = px.scatter_mapbox(houses,
                            lat='lat',
                            lon='long',
                            size = 'price',
                            color_continuous_scale = px.colors.cyclical.IceFire,
                            size_max = 15,
                            zoom = 10)

        fig.update_layout(mapbox_style='open-street-map')
        fig.update_layout(height=600, margin={'r':0, 't':0, 'l':0, 'b':0})  
        st.plotly_chart(fig)

    st.title('Imóveis com possíveis indicadores de preço de venda e lucro')  

    # Agrupar os imóveis por região ( zipcode ) e por sazonalidade ( season )
    # Dentro de cada região/season encontrar a mediana do preço do imóvel.

    df2 = data[['zipcode', 'season', 'price']].groupby(['zipcode', 'season']).median().reset_index()
    df2 = df2.rename(columns={'price': 'price_median_season'})

    buy_houses = pd.merge(buy_houses, df2, how='inner', on=['zipcode', 'season'])

    for i in range(len(buy_houses)):
        if buy_houses.loc[i, 'price'] <= buy_houses.loc[i, 'price_median_season']:
            buy_houses.loc[i, 'selling_price'] = buy_houses.loc[i, 'price'] * 1.30
        elif buy_houses.loc[i, 'price'] > buy_houses.loc[i, 'price_median_season']:
            buy_houses.loc[i, 'selling_price'] = buy_houses.loc[i, 'price'] * 1.10
        else:
            pass

    buy_houses['profit'] = buy_houses['selling_price'] - buy_houses['price']
    st.dataframe(buy_houses[['id','zipcode', 'price','season', 'price_median_season', 'describe_condition', 'selling_price' , 'profit']])
    st.write('O lucro total, será de US$ {} '.format(buy_houses['profit'].sum().round(2)))

    # Mapa de localização
    if st.checkbox('Show Map'):    

        st.title('Properties Overview')
        st.subheader('Location')   

        # Base Map - Folium
        density_map = folium.Map(location=[buy_houses['lat'].mean(), buy_houses['long'].mean()], default_zoom_start=15)
        marker_cluster = MarkerCluster().add_to(density_map)

        for name, row in buy_houses.iterrows():
            folium.Marker([row['lat'], row['long']],
                            popup='Buy price U${0} |Sell Price US$ {1} with profit of US$ {2}. Features: {3} sqft, {4} bedrooms, {5} bathrooms, year built: {6}'.format(
                                row['price'],
                                row['selling_price'],
                                row['profit'],
                                row['sqft_living'],
                                row['bedrooms'],
                                row['bathrooms'],
                                row['yr_built'])).add_to(marker_cluster)

        folium_static(density_map)  

    return None 

def insights(data):

    st.header('Insights')    
    st.sidebar.subheader('Confira os Insights de Negócio ao fim da página, clicando em "Show Insights".')
    if st.checkbox('Show Insights'):           
    
        col1, col2 = st.columns(2)        

        with col1:
            #hipótese 1
            st.subheader('H1')
            st.write('Imóveis que possuem vista para água, são 30% mais caros, em média.')
            st.write('Verdadeira. Imóveis que possuem vista para água são, em média, 212.64% mais caros que os demais.')

            h1 = data.copy()

            h1 = data[['waterfront', 'price']].groupby('waterfront').mean().reset_index()
            h1['percentage'] = h1['price'].pct_change() * 100

            # plot
            h1 = px.bar(data_frame=h1, x='waterfront', y='price',
                        labels={  
                            "waterfront": "Water View", "price": "Price (U$)"
                        }
                        )
            h1.update_xaxes(type='category',
                            tickvals=[0, 1],
                            ticktext=['No', 'Yes']
                            )
            st.plotly_chart(h1, use_container_width=True)

            st.subheader('H2')
            st.write('Imóveis com data de construção abaixo do ano de 1955, são 50% mais baratos, em média.')
            st.write('Falsa. A variação de preços das construções antes de 1955 e depois de 1955 é de somente 0.79%.')        
                                                                    
            h2 = data[['year', 'price']].groupby('year').mean().reset_index()
            h2['pct'] = h2['price'].pct_change() * 100

            #plot
            h2 = px.bar(data_frame=h2, x='year', y='price', color='year',
                        labels={  
                            "ano_construcao": "Construction Year", "price": "Price (U$)"
                        }
                        )

            st.plotly_chart(h2, use_container_width=True)

            st.subheader('H3')
            st.write('Imóveis sem porão possuem área total 40% maior que os imóveis com porão.')
            st.write('Falsa. Imóveis sem porão, são 22.56% maiores, em média.')

            h3 = data[['porao', 'sqft_lot']].groupby('porao').mean().reset_index()
            h3['pct'] = h3['sqft_lot'].pct_change() * 100

            # plot
            h3 = px.bar(data_frame=h3, x='porao', y='sqft_lot', color='porao',
                        labels={  
                            "porao": "Basement", "sqft_lot": "Total property area (sqft)"
                        }
                        )

            st.plotly_chart(h3, use_container_width=True) 

            st.subheader('H4')
            st.write('O crescimento do preço dos imóveis YoY ( Year over Year ) é de 10%.')
            st.write('Falsa. O crescimento do preços dos imóveis varia 0.52% entre os anos.')        
            
            h4 = data[['year_over_year', 'price']].groupby('year_over_year').mean().reset_index()
            h4['pct'] = h4['price'].pct_change() * 100

            h4 = px.bar(data_frame=h4, x='year_over_year', y='price', color='year_over_year',
                        labels={  
                            "price": "Price (U$)"
                        }
                        )

            st.plotly_chart(h4, use_container_width=True)  

        with col2:
            st.subheader('H5')
            st.write('Imóveis com design de maior qualidade em média são mais caros.')
            st.write('Verdadeira. Imóveis com elevado nível de design e construção são 227.21% mais caros, em média.')

            data['design_grade'] = data['grade'].apply(lambda x: 'High' if x > 10 else 'Average or low')        

            h5 = data[['design_grade', 'price']].groupby('design_grade').mean().reset_index()
            h5['pct'] = h5['price'].pct_change() * 100

            #plot
            h5 = px.bar(data_frame=h5, x='design_grade', y='price', color='design_grade',
                        labels={  
                            "price": "Price (U$)", "design_grade": "Level of design and construction"
                        }
                        )

            st.plotly_chart(h5, use_container_width=True) 

            st.subheader('H6')
            st.write('Imóveis que possuem três ou mais vistas são em média 50% mais caros que os demais.')
            st.write('Verdadeira. Imóveis com 3 ou mais vistas, são, em média, 125.34% mais caros que os demais.')        

            data['price_view'] = data['view'].apply(lambda x: 'more than 3' if x >=3 else 'less than 3')

            h6 = data[['price_view', 'price']].groupby('price_view').mean().reset_index()
            h6['pct'] = h6['price'].pct_change() * 100

            #plot
            h10 = px.bar(data_frame=h6, x='price_view', y='price', color='price_view',
                        labels={  
                            "price": "Price (U$)", "e_view": "View quality"
                        }
                        )

            st.plotly_chart(h10, use_container_width=True)  

            st.subheader('H7')
            st.write('Imóveis com 2 ou mais andares são 25% mais caros em média.')
            st.write('Verdadeira. Imóveis com 2 ou mais andares, são, em média, 29.46% mais caros que os demais.')    

            data['price_floors'] = data['floors'].apply(lambda x: "more than 2" if x >= 2 else "less than 2")
            h7 = data[['price_floors', 'price']].groupby('price_floors').mean().reset_index()
            h7['pct'] = h7['price'].pct_change() * 100

            #plot
            h6 = px.bar(data_frame=h7, x='price_floors', y='price', color='price_floors',
                        labels={  
                            "price": "Price (U$)", "price_floors": "Number of floors"
                        }
                        )

            st.plotly_chart(h6, use_container_width=True)


            st.subheader('H8')
            st.write('Imóveis com reforma, são em média 25% mais caros.')
            st.write('Verdadeira. Imóveis com reforma, são em média 43.37% mais caros.')  
            
            h8 = data[['renovated', 'price']].groupby('renovated').mean().reset_index()
            h8['pct'] = h8['price'].pct_change() * 100

            #plot
            h8 = px.bar(data_frame=h8, x='renovated', y='price', color='renovated',
                        labels={  
                            "price": "Price (U$)", "renovated": " "
                        }
                        )

            st.plotly_chart(h8, use_container_width=True)

        return None

if __name__ == '__main__':

    # data extration
    path = ('kc_house_data.csv')
    url = 'https://opendata.arcgis.com/datasets/83fc2e72903343aabff6de8cb445b81c_2.geojson'

    geofile = get_geofile( url )       
    data = get_data(path)

    # transformation
    data = set_feature( data )

    data = clean_data(data)

    overview_data(data)  

    insights(data)