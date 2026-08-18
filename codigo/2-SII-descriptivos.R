
# ---- 0. PAQUETES -----
library(tidyverse)
library(scales)


# ---- 8.  RESULTADOS PAPER 1 ESPAÑOL----
load("datos/SII/SII-2022.RData")

# Tabla fig 1 paper-1
total <- datos_total |> filter(`Año Comercial` < 2020) |> 
  group_by(Year = `Año Comercial`) |> 
  reframe(Companies = `Número de empresas`)


# Grafico a Fig 1 paper-1
cantidad <- ggplot(total, aes(x=Year, y = Companies))+
  geom_line() +
  scale_x_continuous(breaks = c(2005,2007,2009,2011,2013,2015,2017,2019)) +
  scale_y_continuous(labels = comma_format(big.mark = ".")) +
  theme_linedraw()+
  xlab("Año comercial") + ylab("Empresas") +
  theme(text = element_text(family = "Times New Roman"))


# Recodificación
type_table <-  datos_genero |> filter(year < 2020) |> 
  mutate(Tipo = case_when(
    genero == "Masculino" ~ "Empresa Individual",
    genero == "Femenino" ~ "Empresa Individual",
    genero == "Persona Jurídica y otros" ~ "Personalidad jurídica")) |> 
  select(-genero) |> group_by(year, Tipo) |> 
  reframe(Empresas = sum(N)) |> 
  pivot_wider(names_from = year, values_from = Empresas)

type_graph <-  datos_genero |> filter(year < 2020) |> 
  mutate(Tipo = case_when(
    genero == "Masculino" ~ "Empresa Individual",
    genero == "Femenino" ~ "Empresa Individual",
    genero == "Persona Jurídica y otros" ~ "Personalidad jurídica")) |> 
  select(-genero) |> group_by(year, Tipo) |> 
  reframe(Empresas = sum(N)) 

# Grafico 2 fig 1 paper-1
tipo <- ggplot(type_graph, aes(fill = Tipo, x = year, y = Empresas)) +
  geom_bar(position="fill", stat="identity") +
  scale_x_continuous(breaks = c(2005,2007,2009,2011,2013,2015,2017,2019)) +
  scale_y_continuous(labels = scales::percent) +
  scale_fill_brewer(palette = "Set2") +
  xlab("Año comercial") + ylab("Empresas") +
  theme(legend.position = "bottom") +
  theme(text = element_text(family = "Times New Roman")) 

