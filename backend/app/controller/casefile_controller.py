from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from backend.app.services.neo4j_client import driver
from backend.app.services.keycloak_service import get_current_user

router = APIRouter(prefix="/casefiles", tags=["casefiles"])

# --- Pydantic schemas ---
class CaseFileBase(BaseModel):
    id: str
    title: str
    category: str
    created_by: str = Field(default_factory=lambda: get_current_user()["preferred_username"])
    created_at: datetime = Field(default_factory=datetime.now)
    postCount: int = Field(default=0)


class CaseFileCreate(CaseFileBase):
    channels: List[str]
    topics: List[str]
    terms: List[str]
    duration: int = Field(gt=0)


class CaseFileResponse(CaseFileCreate):
    monitoring_until: datetime


class CaseFileAnalysis(BaseModel):
    casefile: CaseFileBase
    statistics: dict
    topics: List[str]
    terms: List[dict]

class Config:
    from_attributes = True

#TODO: Filter, Search, Update, Sort

@router.post("/", response_model=CaseFileResponse)
async def create_casefile(
        casefile: CaseFileCreate,
        current_user=Depends(get_current_user)
):
    async with driver.session() as session:
        async with session.begin_transaction() as tx:
            try:
                # Validiere Channels
                channels = await validate_channels(casefile.channels)

                # Erstelle CaseFile
                result = await tx.run("""
                CREATE (cf:CaseFile {
                    id: $id,
                    title: $title,
                    created_at: $created_at,
                    created_by: $created_by,
                    category: $category,
                    postCount: $postCount,
                    monitoring_until: datetime() + duration('P' + $duration + 'D')
                })

                WITH cf
                UNWIND $topics as topic
                MERGE (t:Topic {text: topic})
                CREATE (cf)-[:HAS_TOPIC]->(t)

                WITH cf
                UNWIND $terms as term
                MERGE (term:Term {text: term})
                CREATE (cf)-[:HAS_TERM]->(term)

                WITH cf
                UNWIND $channels as channel_id
                MATCH (ch:Channel {channel_id: channel_id})
                CREATE (cf)-[:MONITORS]->(ch)

                RETURN cf {
                    .*,
                    channels: $channels,
                    topics: $topics,
                    terms: $terms
                } as casefile
                """,
                                      **casefile.model_dump(),
                                      duration=str(casefile.duration)
                                      )

                await tx.commit()
                return await result.single()

            except Exception as e:
                await tx.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )

async def validate_channels(channels: List[str]) -> List[str]:
    async with driver.session() as session:
        result = await session.run("""
        UNWIND $channels as channel_id
        MATCH (ch:Channel {channel_id: channel_id})
        RETURN collect(ch.channel_id) as valid_channels
        """, channels=channels)

        valid_channels = (await result.single())["valid_channels"]
        if len(valid_channels) != len(channels):
            raise HTTPException(
                status_code=400,
                detail="Some channels do not exist"
            )
        return valid_channels


@router.get("/{casefile_id}/analysis")
async def get_casefile_analysis(casefile_id: str, current_user=Depends(get_current_user)):
    async with driver.session() as session:
        result = await session.run("""
            MATCH (cf:CaseFile {id: $id})
            MATCH (cf)-[:HAS_TOPIC]->(t:Topic)
            MATCH (cf)-[:HAS_TERM]->(term:Term)
            OPTIONAL MATCH (m:Message)-[:MATCHES_TERM]->(term)

            WITH cf, t, term, m,
                 datetime() - duration('P1D') as last_24h

            RETURN {
                casefile: {
                    id: cf.id,
                    title: cf.title,
                    category: cf.category,
                    created_at: cf.created_at,
                    monitoring_until: cf.monitoring_until
                },
                statistics: {
                    total_messages: count(DISTINCT m),
                    messages_24h: count(DISTINCT (
                        CASE WHEN m.date > last_24h THEN m ELSE NULL END
                    )),
                    term_matches: count(DISTINCT (m)-[:MATCHES_TERM]->(term))
                },
                topics: collect(DISTINCT t.text),
                terms: collect(DISTINCT {
                    text: term.text,
                    matches: count(DISTINCT m)
                })
            }
        """, id=casefile_id)

        analysis = await result.single()
        if not analysis:
            raise HTTPException(status_code=404, detail="Casefile not found")
        return analysis


@router.get("/", response_model=List[CaseFileResponse])
async def get_casefiles(current_user=Depends(get_current_user)):
    async with driver.session() as session:
        result = await session.run("""
            MATCH (cf:CaseFile)
            RETURN {
                id: cf.id,
                title: cf.title,
                created_at: cf.created_at,
                created_by: cf.created_by,
                category: cf.category,
                postCount: cf.postCount,
                monitoring_until: cf.monitoring_until
            } as casefile
            ORDER BY cf.created_at DESC
        """)
        return await result.data()


@router.post("/{casefile_id}/update-matches")
async def update_matches(
        casefile_id: str,
        current_user=Depends(get_current_user)
):
    async with driver.session() as session:
        await session.run("""
        MATCH (cf:CaseFile {id: $id})
        MATCH (cf)-[:HAS_TERM]->(term:Term)
        CALL {
            WITH cf, term
            MATCH (m:Message)
            WHERE m.text CONTAINS term.text 
            AND m.date <= cf.monitoring_until
            AND NOT (m)-[:MATCHES_TERM]->(term)
            WITH m, term
            LIMIT 1000  // Batch-Size
            CREATE (m)-[:MATCHES_TERM]->(term)
            CREATE (cf)-[:RELEVANT_MESSAGE]->(m)
        } IN TRANSACTIONS OF 100 ROWS
        """, id=casefile_id)

        return {"success": True}


@router.delete("/{casefile_id}")
async def delete_casefile(casefile_id: str, current_user=Depends(get_current_user)):
    async with driver.session() as session:
        result = await session.run("""
            MATCH (cf:CaseFile {id: $id})
            DETACH DELETE cf
            RETURN count(cf) as deleted
        """, id=casefile_id)
        if (await result.single())["deleted"] == 0:
            raise HTTPException(status_code=404, detail="Casefile not found")
        return {"success": True}
