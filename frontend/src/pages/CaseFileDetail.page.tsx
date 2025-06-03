import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader, Text, Title, Grid, Card, Tabs, Table, Checkbox, ScrollArea, Stack } from '@mantine/core';
import BreadcrumbsBar from '@/components/BreadcrumbsBar/BreadcrumbsBar';
import classes from './CaseFileDetail.module.css';
import {
  IconMap,
  IconMessage,
  IconEye,
} from '@tabler/icons-react';

const apiUrl = import.meta.env.VITE_API_URL;

export function CaseFileDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseFile, setCaseFile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedRows, setSelectedRows] = useState<number[]>([]);

  useEffect(() => {
    fetch(`${apiUrl ? apiUrl : 'http://localhost:8000/api'}/casefiles/${id}`)
      .then((res) => res.json())
      .then((data) => {
        setCaseFile(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <Loader />;
  }
  if (!caseFile) {
    return <Text>Case file not found.</Text>;
  }  

  const elements = [
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 1 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 2 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 3 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 4 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 5 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 6 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 7 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 8 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 9 },
    { message: "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren,", author: "Max Mustermann", tgchannel: 'insider_nachrichten', id: 10 },
  ];

  const rows = elements.map((element) => (
    <Table.Tr
      key={element.id}
      bg={selectedRows.includes(element.id) ? 'var(--mantine-color-blue-light)' : undefined}
    >
      <Table.Td>
        <Checkbox
          aria-label="Select row"
          checked={selectedRows.includes(element.id)}
          onChange={(event) =>
            setSelectedRows(
              event.currentTarget.checked
                ? [...selectedRows, element.id]
                : selectedRows.filter((position) => position !== element.id)
            )
          }
        />
      </Table.Td>
      <Table.Td>{element.message}</Table.Td>
      <Table.Td>{element.author}</Table.Td>
      <Table.Td>{element.tgchannel}</Table.Td>
    </Table.Tr>
  ));

  const topicsCheckboxes = caseFile.topics.map((element: string) => (
    <Checkbox
      label={element}
    />  
  ));
  const termsCheckboxes = caseFile.terms.map((element: string) => (
    <Checkbox
      label={element}
    />  
  ));
  const tgChannelsCheckboxes = caseFile.tgchannels.map((element: string) => (
    <Checkbox
      label={element}
    />  
  ));

  return (
    <div>
      <BreadcrumbsBar overrides={{ [`/cases/${caseFile.id}`]: caseFile.title }} />
      <Title mb="xl">{caseFile.title}</Title>

      <Grid>
        <Grid.Col span={3}>
          <Grid>
            <Grid.Col>
              <Card withBorder p="xl" radius="md" className={classes.card}>
                <div className={classes.inner}>
                  <Stack>
                    <Text>Topics:</Text>
                    {topicsCheckboxes}
                  </Stack>
                </div>
              </Card>
            </Grid.Col>
            <Grid.Col>
              <Card withBorder p="xl" radius="md" className={classes.card}>
                <div className={classes.inner}>
                  <Stack>
                    <Text>Terms:</Text>
                    {termsCheckboxes}
                  </Stack>
                </div>
              </Card>
            </Grid.Col>
            <Grid.Col>
              <Card withBorder p="xl" radius="md" className={classes.card}>
                <div className={classes.inner}>
                  <Stack>
                    <Text>Telegram Channels:</Text>
                    {tgChannelsCheckboxes}
                  </Stack>
                </div>
              </Card>
            </Grid.Col>
          </Grid>
        </Grid.Col>
        <Grid.Col span={9}>
          <Card withBorder radius="md" className={classes.card}>
            <div className={classes.inner}>
              <Tabs defaultValue="messages" w="100%">
                <Tabs.List>
                  <Tabs.Tab value="messages" leftSection={<IconMessage size={12} />}>
                    Messages
                  </Tabs.Tab>
                  <Tabs.Tab value="visuals" leftSection={<IconEye size={12} />}>
                    Visuals
                  </Tabs.Tab>
                  <Tabs.Tab value="map" leftSection={<IconMap size={12} />}>
                    Map
                  </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="messages" mt="md">
                  <ScrollArea h={400}>
                    <Table>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th />
                          <Table.Th>Message</Table.Th>
                          <Table.Th>Author</Table.Th>
                          <Table.Th>Channel/Group</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>{rows}</Table.Tbody>
                    </Table>
                  </ScrollArea>
                </Tabs.Panel>

                <Tabs.Panel value="visuals" mt="md">
                  Visuals tab content
                </Tabs.Panel>

                <Tabs.Panel value="map" mt="md">
                  Map tab content
                </Tabs.Panel>
              </Tabs>
            </div>
          </Card>
        </Grid.Col>
      </Grid>
    </div>
  );
}
