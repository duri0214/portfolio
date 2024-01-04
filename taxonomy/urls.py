from django.urls import path

from taxonomy.views import IndexView, KingdomCreateView, PhylumCreateView, ClassificationCreateView, FamilyCreateView, \
    GenusCreateView, SpeciesCreateView, BreedCreateView, TagCreateView, BreedTagUpdateView

app_name = 'txo'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('kingdom/create/', KingdomCreateView.as_view(), name='kingdom_create'),
    path('phylum/create/', PhylumCreateView.as_view(), name='phylum_create'),
    path('classification/create/', ClassificationCreateView.as_view(), name='classification_create'),
    path('family/create/', FamilyCreateView.as_view(), name='family_create'),
    path('genus/create/', GenusCreateView.as_view(), name='genus_create'),
    path('species/create/', SpeciesCreateView.as_view(), name='species_create'),
    path('breed/create/', BreedCreateView.as_view(), name='breed_create'),
    path('tag/create/', TagCreateView.as_view(), name='tag_create'),
    path('breed_tag/update/', BreedTagUpdateView.as_view(), name='breed_tags_update'),
]
