
# ---- 0. LECTURA DE DATOS Y PAQUETES ----
library(tidyverse)

# Leer bbdd histórica
forbes <- readr::read_csv("datos/kaggle/forbes/all_billionaires_1997_2023.csv")

# ---- 1. EDICIÓN DE VARIABLES ----

# Editar variable net_worth como numerica, substrayendo espacios en blancos y B.
forbes$net_worth <- as.numeric(str_sub(forbes$net_worth , end = -3))


# ---- 2. RESULTADOS DE INTERÉS: CHILE -----

# Edición de variable nombre

nombres <- forbes |> filter(country_of_citizenship == "Chile") |> reframe(unique(full_name))

forbes <- forbes %>% 
  mutate(nombre = case_when(full_name == "Eliodoro Matte & family" ~ "Matte",
                            full_name == "Sebastian Pinera" ~ "Piñera",
                            full_name == "Iris Fontbona & family" ~ "Luksic Fontbona",
                            full_name == "Eliodoro, Bernardo & Patricia Matte" ~ "Matte",
                            full_name == "Horst Paulmann & family" ~ "Paulmann",
                            full_name == "Eliodoro Matte" ~ "Matte",
                            full_name == "Roberto Angelini Rossi" ~ "Angelini",
                            full_name == "Bernardo Matte" ~ "Matte",
                            full_name == "Patricia Matte" ~ "Matte",
                            full_name == "Maria Luisa Solari Falabella & family" ~ "Solari",
                            full_name == "Juan Cuneo Solari & family" ~ "Solari",
                            full_name == "Teresa Matilde Solari Falabella & family" ~ "Solari",
                            full_name == "Piero Solari Donaggio & family" ~ "Solari",
                            full_name == "Alvaro Saieh Bendeck" ~ "Saieh",
                            full_name == "Sebastian Piñera" ~ "Piñera",
                            full_name == "Luis Enrique Yarur Rey" ~ "Yarur",
                            full_name == "Patricia Angelini Rossi" ~ "Angelini",
                            full_name == "Julio Ponce Lerou" ~ "Ponce Lerou",
                            full_name == "Sebastian Piñera & family" ~ "Piñera",
                            full_name == "Jean Salata" ~ "Salata",
                            full_name == "Alvaro Saieh" ~ "Saieh"))


## GRÁFICO 4
# Millonarios de Chile, evolución individual de riqueza
forbes |> filter(country_of_citizenship == "Chile") |> 
  filter(year > 1999) |> filter(year < 2020) |>
  ggplot(aes(x = year, y = net_worth, color = nombre)) +
  geom_line() +
  scale_x_continuous(breaks = 2000:2019) +
  labs(x = 'Año', y = 'Riqueza en USD billones', 
       color = "Multimillonario") +
  theme_light() +  
  theme(text = element_text(family = "Times New Roman"),
        legend.position="right",
        axis.text.x = element_text(angle = 45, vjust = 0.5))


## TABLA 5

library(gt)

# Tabla de millonarios de país específico 2019
forbes |> filter(country_of_citizenship == "Chile" & year == 2019) |> 
  select(full_name, rank, net_worth, business_category) |>  
  gt::gt() |> tab_header(
    title = md("Listado de Billonarios 2019"),
    subtitle = md("País: Chile")) |> 
  tab_source_note(source_note = "Elaboración propia con base en Ranking Forbes 1997-2019")
