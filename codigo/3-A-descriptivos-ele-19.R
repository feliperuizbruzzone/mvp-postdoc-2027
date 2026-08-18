# ---- 0. CARGA DE DATOS Y PAQUETES ----
## Paquetes
pacman::p_load(tidyverse, srvyr,janitor, summarytools, scales)
## Datos
ele_2019 <- readRDS("datos/ele/ele_2019.rds")

# Gráfico 3.1 con resultados ponderados
ele_2019 %>% as_survey(weights = fe_t) %>% 
  group_by(grupo) %>% 
  summarize(n = survey_total()) %>% 
  select(-n_se) %>% 
  mutate(freq = n / sum(n)) %>% 
  ggplot(aes(y= freq, x = grupo,label = scales::percent(freq))) +
  geom_bar(stat = 'identity') +
  geom_text(vjust = 1.25, colour = "white", size = 3) +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1)) +
  labs(x = 'Organización propiedad', y = '%', 
       caption = "Elaboración propia con base en ELE 2019") +
  theme_linedraw()

#### 3.2. Tabla DISTRIBUCIÓN DEL PATRIMONIO 2019
ele_2019 %>% as_survey_design(weights = fe_t) %>% 
  group_by(grupo) %>% summarise(
    Patrimonio = survey_total(patrim_2019)) %>% 
  select(-Patrimonio_se) %>% 
  dplyr::mutate(prop = Patrimonio/sum(Patrimonio)*100) %>% 
  janitor::adorn_totals(where = "row")
